from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import aiosqlite


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value)


@dataclass
class Endpoint:
    id: int
    name: str
    agent_token: str
    hostname: Optional[str]
    last_seen_at: Optional[str]
    alerts_enabled: bool
    created_at: str


@dataclass
class Monitor:
    id: int
    endpoint_id: int
    monitor_key: str
    name: Optional[str]
    last_seen_at: Optional[str]
    is_connected: bool


@dataclass
class Incident:
    id: int
    endpoint_id: int
    monitor_id: int
    started_at: str
    ended_at: Optional[str]
    duration_sec: Optional[int]
    monitor_name: Optional[str] = None
    monitor_key: Optional[str] = None
    endpoint_name: Optional[str] = None


@dataclass
class OfflineIncident:
    id: int
    endpoint_id: int
    started_at: str
    ended_at: Optional[str]
    duration_sec: Optional[int]
    endpoint_name: Optional[str] = None


@dataclass
class HeartbeatChange:
    kind: str
    endpoint: Endpoint
    monitor: Optional[Monitor] = None
    duration_sec: Optional[int] = None


class Database:
    def __init__(self, path: str) -> None:
        self.path = path
        self._db: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA foreign_keys = ON")
        await self._init_schema()

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("Database is not connected")
        return self._db

    async def _init_schema(self) -> None:
        await self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS endpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                agent_token TEXT NOT NULL UNIQUE,
                hostname TEXT,
                last_seen_at TEXT,
                alerts_enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS monitors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint_id INTEGER NOT NULL REFERENCES endpoints(id) ON DELETE CASCADE,
                monitor_key TEXT NOT NULL,
                name TEXT,
                last_seen_at TEXT,
                is_connected INTEGER NOT NULL DEFAULT 1,
                UNIQUE(endpoint_id, monitor_key)
            );

            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint_id INTEGER NOT NULL REFERENCES endpoints(id) ON DELETE CASCADE,
                monitor_id INTEGER NOT NULL REFERENCES monitors(id) ON DELETE CASCADE,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                duration_sec INTEGER
            );

            CREATE TABLE IF NOT EXISTS endpoint_offline_incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint_id INTEGER NOT NULL REFERENCES endpoints(id) ON DELETE CASCADE,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                duration_sec INTEGER
            );

            CREATE INDEX IF NOT EXISTS idx_incidents_endpoint
                ON incidents(endpoint_id, started_at DESC);
            CREATE INDEX IF NOT EXISTS idx_offline_endpoint
                ON endpoint_offline_incidents(endpoint_id, started_at DESC);
            """
        )
        await self.db.commit()

    def _endpoint_from_row(self, row: aiosqlite.Row) -> Endpoint:
        return Endpoint(
            id=row["id"],
            name=row["name"],
            agent_token=row["agent_token"],
            hostname=row["hostname"],
            last_seen_at=row["last_seen_at"],
            alerts_enabled=bool(row["alerts_enabled"]),
            created_at=row["created_at"],
        )

    def _monitor_from_row(self, row: aiosqlite.Row) -> Monitor:
        return Monitor(
            id=row["id"],
            endpoint_id=row["endpoint_id"],
            monitor_key=row["monitor_key"],
            name=row["name"],
            last_seen_at=row["last_seen_at"],
            is_connected=bool(row["is_connected"]),
        )

    async def create_endpoint(self, name: str) -> Endpoint:
        token = secrets.token_urlsafe(24)
        created = to_iso(utcnow())
        cur = await self.db.execute(
            """
            INSERT INTO endpoints (name, agent_token, created_at)
            VALUES (?, ?, ?)
            """,
            (name, token, created),
        )
        await self.db.commit()
        endpoint = await self.get_endpoint(cur.lastrowid)
        assert endpoint is not None
        return endpoint

    async def get_endpoint(self, endpoint_id: int) -> Optional[Endpoint]:
        cur = await self.db.execute(
            "SELECT * FROM endpoints WHERE id = ?",
            (endpoint_id,),
        )
        row = await cur.fetchone()
        return self._endpoint_from_row(row) if row else None

    async def get_endpoint_by_token(self, token: str) -> Optional[Endpoint]:
        cur = await self.db.execute(
            "SELECT * FROM endpoints WHERE agent_token = ?",
            (token,),
        )
        row = await cur.fetchone()
        return self._endpoint_from_row(row) if row else None

    async def list_endpoints(self) -> list[Endpoint]:
        cur = await self.db.execute("SELECT * FROM endpoints ORDER BY name COLLATE NOCASE")
        rows = await cur.fetchall()
        return [self._endpoint_from_row(r) for r in rows]

    async def set_alerts_enabled(self, endpoint_id: int, enabled: bool) -> Optional[Endpoint]:
        await self.db.execute(
            "UPDATE endpoints SET alerts_enabled = ? WHERE id = ?",
            (1 if enabled else 0, endpoint_id),
        )
        await self.db.commit()
        return await self.get_endpoint(endpoint_id)

    async def delete_endpoint(self, endpoint_id: int) -> bool:
        # Явно чистим дочерние строки: старые БД могли быть созданы без ON DELETE CASCADE.
        await self.db.execute(
            "DELETE FROM incidents WHERE endpoint_id = ?",
            (endpoint_id,),
        )
        await self.db.execute(
            "DELETE FROM endpoint_offline_incidents WHERE endpoint_id = ?",
            (endpoint_id,),
        )
        await self.db.execute(
            "DELETE FROM monitors WHERE endpoint_id = ?",
            (endpoint_id,),
        )
        cur = await self.db.execute(
            "DELETE FROM endpoints WHERE id = ?",
            (endpoint_id,),
        )
        await self.db.commit()
        return cur.rowcount > 0

    async def list_monitors(self, endpoint_id: int) -> list[Monitor]:
        cur = await self.db.execute(
            "SELECT * FROM monitors WHERE endpoint_id = ? ORDER BY name COLLATE NOCASE",
            (endpoint_id,),
        )
        rows = await cur.fetchall()
        return [self._monitor_from_row(r) for r in rows]

    async def get_open_monitor_incidents(self, endpoint_id: int) -> list[Incident]:
        cur = await self.db.execute(
            """
            SELECT i.*, m.name AS monitor_name, m.monitor_key AS monitor_key
            FROM incidents i
            JOIN monitors m ON m.id = i.monitor_id
            WHERE i.endpoint_id = ? AND i.ended_at IS NULL
            ORDER BY i.started_at DESC
            """,
            (endpoint_id,),
        )
        rows = await cur.fetchall()
        return [
            Incident(
                id=r["id"],
                endpoint_id=r["endpoint_id"],
                monitor_id=r["monitor_id"],
                started_at=r["started_at"],
                ended_at=r["ended_at"],
                duration_sec=r["duration_sec"],
                monitor_name=r["monitor_name"],
                monitor_key=r["monitor_key"],
            )
            for r in rows
        ]

    async def get_open_offline_incident(self, endpoint_id: int) -> Optional[OfflineIncident]:
        cur = await self.db.execute(
            """
            SELECT * FROM endpoint_offline_incidents
            WHERE endpoint_id = ? AND ended_at IS NULL
            ORDER BY started_at DESC LIMIT 1
            """,
            (endpoint_id,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return OfflineIncident(
            id=row["id"],
            endpoint_id=row["endpoint_id"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            duration_sec=row["duration_sec"],
        )

    async def process_heartbeat(
        self,
        endpoint: Endpoint,
        hostname: Optional[str],
        monitors: list[dict[str, str]],
    ) -> list[HeartbeatChange]:
        now = to_iso(utcnow())
        changes: list[HeartbeatChange] = []

        await self.db.execute(
            """
            UPDATE endpoints
            SET last_seen_at = ?, hostname = COALESCE(?, hostname)
            WHERE id = ?
            """,
            (now, hostname, endpoint.id),
        )

        open_offline = await self.get_open_offline_incident(endpoint.id)
        if open_offline:
            started = parse_iso(open_offline.started_at)
            duration = int((utcnow() - started).total_seconds()) if started else 0
            await self.db.execute(
                """
                UPDATE endpoint_offline_incidents
                SET ended_at = ?, duration_sec = ?
                WHERE id = ?
                """,
                (now, duration, open_offline.id),
            )
            refreshed = await self.get_endpoint(endpoint.id)
            assert refreshed is not None
            changes.append(
                HeartbeatChange(
                    kind="agent_online",
                    endpoint=refreshed,
                    duration_sec=duration,
                )
            )

        seen_keys = {m["key"] for m in monitors}
        existing = {m.monitor_key: m for m in await self.list_monitors(endpoint.id)}

        for item in monitors:
            key = item["key"]
            name = item.get("name") or key
            if key in existing:
                mon = existing[key]
                await self.db.execute(
                    """
                    UPDATE monitors
                    SET name = ?, last_seen_at = ?, is_connected = 1
                    WHERE id = ?
                    """,
                    (name, now, mon.id),
                )
                if not mon.is_connected:
                    cur = await self.db.execute(
                        """
                        SELECT * FROM incidents
                        WHERE monitor_id = ? AND ended_at IS NULL
                        ORDER BY started_at DESC LIMIT 1
                        """,
                        (mon.id,),
                    )
                    open_inc = await cur.fetchone()
                    duration = None
                    if open_inc:
                        started = parse_iso(open_inc["started_at"])
                        duration = int((utcnow() - started).total_seconds()) if started else 0
                        await self.db.execute(
                            """
                            UPDATE incidents
                            SET ended_at = ?, duration_sec = ?
                            WHERE id = ?
                            """,
                            (now, duration, open_inc["id"]),
                        )
                    updated = Monitor(
                        id=mon.id,
                        endpoint_id=mon.endpoint_id,
                        monitor_key=mon.monitor_key,
                        name=name,
                        last_seen_at=now,
                        is_connected=True,
                    )
                    refreshed = await self.get_endpoint(endpoint.id)
                    assert refreshed is not None
                    changes.append(
                        HeartbeatChange(
                            kind="monitor_online",
                            endpoint=refreshed,
                            monitor=updated,
                            duration_sec=duration,
                        )
                    )
            else:
                await self.db.execute(
                    """
                    INSERT INTO monitors
                        (endpoint_id, monitor_key, name, last_seen_at, is_connected)
                    VALUES (?, ?, ?, ?, 1)
                    """,
                    (endpoint.id, key, name, now),
                )

        for key, mon in existing.items():
            if key in seen_keys or not mon.is_connected:
                continue
            await self.db.execute(
                "UPDATE monitors SET is_connected = 0 WHERE id = ?",
                (mon.id,),
            )
            await self.db.execute(
                """
                INSERT INTO incidents (endpoint_id, monitor_id, started_at)
                VALUES (?, ?, ?)
                """,
                (endpoint.id, mon.id, now),
            )
            disconnected = Monitor(
                id=mon.id,
                endpoint_id=mon.endpoint_id,
                monitor_key=mon.monitor_key,
                name=mon.name,
                last_seen_at=mon.last_seen_at,
                is_connected=False,
            )
            refreshed = await self.get_endpoint(endpoint.id)
            assert refreshed is not None
            changes.append(
                HeartbeatChange(
                    kind="monitor_offline",
                    endpoint=refreshed,
                    monitor=disconnected,
                )
            )

        await self.db.commit()
        refreshed = await self.get_endpoint(endpoint.id)
        assert refreshed is not None
        return changes

    async def mark_stale_endpoints_offline(
        self,
        threshold_sec: int,
    ) -> list[HeartbeatChange]:
        cutoff = utcnow() - timedelta(seconds=threshold_sec)
        changes: list[HeartbeatChange] = []
        for endpoint in await self.list_endpoints():
            if not endpoint.last_seen_at:
                continue
            last_seen = parse_iso(endpoint.last_seen_at)
            if last_seen is None or last_seen >= cutoff:
                continue
            open_offline = await self.get_open_offline_incident(endpoint.id)
            if open_offline:
                continue
            now = to_iso(utcnow())
            await self.db.execute(
                """
                INSERT INTO endpoint_offline_incidents (endpoint_id, started_at)
                VALUES (?, ?)
                """,
                (endpoint.id, now),
            )
            changes.append(
                HeartbeatChange(kind="agent_offline", endpoint=endpoint)
            )
        if changes:
            await self.db.commit()
        return changes

    async def list_downtime_windows(
        self,
        endpoint_id: int,
        since: datetime,
        until: Optional[datetime] = None,
    ) -> list[tuple[datetime, Optional[datetime]]]:
        """Intervals when endpoint was not fully online (monitor off or agent offline)."""
        end = until or utcnow()
        since_s = to_iso(since)
        until_s = to_iso(end)
        windows: list[tuple[datetime, Optional[datetime]]] = []

        cur = await self.db.execute(
            """
            SELECT started_at, ended_at FROM incidents
            WHERE endpoint_id = ?
              AND started_at < ?
              AND (ended_at IS NULL OR ended_at > ?)
            ORDER BY started_at ASC
            """,
            (endpoint_id, until_s, since_s),
        )
        for row in await cur.fetchall():
            start = parse_iso(row["started_at"])
            if start is None:
                continue
            windows.append((start, parse_iso(row["ended_at"])))

        cur = await self.db.execute(
            """
            SELECT started_at, ended_at FROM endpoint_offline_incidents
            WHERE endpoint_id = ?
              AND started_at < ?
              AND (ended_at IS NULL OR ended_at > ?)
            ORDER BY started_at ASC
            """,
            (endpoint_id, until_s, since_s),
        )
        for row in await cur.fetchall():
            start = parse_iso(row["started_at"])
            if start is None:
                continue
            windows.append((start, parse_iso(row["ended_at"])))

        return windows

    async def list_incidents(
        self,
        endpoint_id: Optional[int],
        since: Optional[datetime],
        limit: int = 50,
    ) -> list[Incident]:
        clauses = ["1=1"]
        params: list[Any] = []
        if endpoint_id is not None:
            clauses.append("i.endpoint_id = ?")
            params.append(endpoint_id)
        if since is not None:
            clauses.append("i.started_at >= ?")
            params.append(to_iso(since))
        params.append(limit)
        sql = f"""
            SELECT i.*, m.name AS monitor_name, m.monitor_key AS monitor_key,
                   e.name AS endpoint_name
            FROM incidents i
            JOIN monitors m ON m.id = i.monitor_id
            JOIN endpoints e ON e.id = i.endpoint_id
            WHERE {' AND '.join(clauses)}
            ORDER BY i.started_at DESC
            LIMIT ?
        """
        cur = await self.db.execute(sql, params)
        rows = await cur.fetchall()
        return [
            Incident(
                id=r["id"],
                endpoint_id=r["endpoint_id"],
                monitor_id=r["monitor_id"],
                started_at=r["started_at"],
                ended_at=r["ended_at"],
                duration_sec=r["duration_sec"],
                monitor_name=r["monitor_name"],
                monitor_key=r["monitor_key"],
                endpoint_name=r["endpoint_name"],
            )
            for r in rows
        ]

    async def stats(self, since: Optional[datetime] = None) -> list[dict[str, Any]]:
        downtime_expr = """
            COALESCE(SUM(
                CASE
                    WHEN i.duration_sec IS NOT NULL THEN i.duration_sec
                    WHEN i.id IS NOT NULL AND i.ended_at IS NULL THEN
                        CAST(
                            (julianday('now') - julianday(i.started_at)) * 86400
                            AS INTEGER
                        )
                    ELSE 0
                END
            ), 0) AS total_downtime_sec
        """
        if since is not None:
            cur = await self.db.execute(
                f"""
                SELECT e.id, e.name,
                       COUNT(i.id) AS incident_count,
                       {downtime_expr}
                FROM endpoints e
                LEFT JOIN incidents i
                    ON i.endpoint_id = e.id AND i.started_at >= ?
                GROUP BY e.id
                ORDER BY e.name COLLATE NOCASE
                """,
                (to_iso(since),),
            )
        else:
            cur = await self.db.execute(
                f"""
                SELECT e.id, e.name,
                       COUNT(i.id) AS incident_count,
                       {downtime_expr}
                FROM endpoints e
                LEFT JOIN incidents i ON i.endpoint_id = e.id
                GROUP BY e.id
                ORDER BY e.name COLLATE NOCASE
                """
            )
        rows = await cur.fetchall()
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "incident_count": r["incident_count"],
                "total_downtime_sec": r["total_downtime_sec"],
            }
            for r in rows
        ]

    async def endpoint_status(self, endpoint: Endpoint, offline_threshold_sec: int) -> str:
        if await self.get_open_offline_incident(endpoint.id):
            return "agent_offline"
        if endpoint.last_seen_at:
            last_seen = parse_iso(endpoint.last_seen_at)
            if last_seen and (utcnow() - last_seen).total_seconds() > offline_threshold_sec:
                return "agent_offline"
        elif not endpoint.last_seen_at:
            return "unknown"
        open_incs = await self.get_open_monitor_incidents(endpoint.id)
        if open_incs:
            return "monitor_offline"
        monitors = await self.list_monitors(endpoint.id)
        if not monitors:
            return "unknown"
        return "ok"
