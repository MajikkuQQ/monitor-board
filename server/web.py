from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from server.alerts import format_duration
from server.config import Settings
from server.db import Database, Endpoint, parse_iso

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

web_router = APIRouter(tags=["web"])


def get_db(request: Request) -> Database:
    return request.app.state.db


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def web_password(settings: Settings) -> str:
    return settings.web_password or settings.admin_api_key


def is_authenticated(request: Request) -> bool:
    return bool(request.session.get("web_auth"))


async def require_web_auth(request: Request) -> None:
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Unauthorized")


def fmt_ts(value: Optional[str]) -> str:
    dt = parse_iso(value)
    if not dt:
        return "—"
    return dt.astimezone().strftime("%d.%m.%Y %H:%M:%S")


def format_duration_short(seconds: Optional[int]) -> str:
    if seconds is None:
        return "?"
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}ч {minutes}м"
    if minutes:
        return f"{minutes}м"
    return f"{secs}с"


def _interval_overlaps(
    start: datetime,
    end: datetime,
    win_start: datetime,
    win_end: Optional[datetime],
) -> bool:
    real_end = win_end or datetime.now(timezone.utc)
    return start < real_end and end > win_start


async def build_uptime_timeline(
    db: Database,
    endpoint: Endpoint,
    *,
    hours: int = 48,
    ticks: int = 72,
) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=hours)
    step = (now - window_start) / ticks
    downtime = await db.list_downtime_windows(endpoint.id, window_start, now)

    known_from = parse_iso(endpoint.created_at) or window_start
    if endpoint.last_seen_at:
        first_seen = parse_iso(endpoint.last_seen_at)
        if first_seen and first_seen < known_from:
            known_from = first_seen

    raw: list[str] = []
    for i in range(ticks):
        seg_start = window_start + step * i
        seg_end = window_start + step * (i + 1)
        if seg_end <= known_from:
            raw.append("mute")
            continue
        down = any(
            _interval_overlaps(seg_start, seg_end, w_start, w_end)
            for w_start, w_end in downtime
        )
        raw.append("bad" if down else "ok")

    # If never seen, and currently unknown/offline without history, tint last ticks.
    if not endpoint.last_seen_at and not downtime:
        raw = ["mute"] * ticks

    labels = {"ok": "Онлайн", "bad": "Оффлайн", "mute": "Нет данных"}
    timeline: list[dict[str, Any]] = []
    for i, state in enumerate(raw):
        seg_end = window_start + step * (i + 1)
        run = 1
        j = i - 1
        while j >= 0 and raw[j] == state:
            run += 1
            j -= 1
        duration_sec = int(run * step.total_seconds())
        local = seg_end.astimezone()
        timeline.append(
            {
                "s": state,
                "t": local.strftime("%H:%M"),
                "label": f"{labels[state]} · {format_duration_short(duration_sec)}",
            }
        )
    return timeline


async def build_overview(db: Database, settings: Settings) -> dict[str, Any]:
    endpoints = await db.list_endpoints()
    items: list[dict[str, Any]] = []
    counts = {"ok": 0, "monitor_offline": 0, "agent_offline": 0, "unknown": 0}

    for ep in endpoints:
        status = await db.endpoint_status(ep, settings.offline_threshold_sec)
        counts[status] = counts.get(status, 0) + 1
        monitors = await db.list_monitors(ep.id)
        open_incs = await db.get_open_monitor_incidents(ep.id)
        uptime = await build_uptime_timeline(db, ep)
        items.append(
            {
                "id": ep.id,
                "name": ep.name,
                "hostname": ep.hostname,
                "last_seen_at": ep.last_seen_at,
                "last_seen_label": fmt_ts(ep.last_seen_at),
                "status": status,
                "alerts_enabled": ep.alerts_enabled,
                "monitors_total": len(monitors),
                "monitors_on": sum(1 for m in monitors if m.is_connected),
                "open_incidents": len(open_incs),
                "uptime": uptime,
            }
        )

    return {
        "generated_at": datetime.now().astimezone().strftime("%d.%m.%Y %H:%M:%S"),
        "counts": counts,
        "endpoints": items,
    }


async def build_endpoint_detail(
    db: Database,
    settings: Settings,
    endpoint: Endpoint,
    days: int = 7,
) -> dict[str, Any]:
    status = await db.endpoint_status(endpoint, settings.offline_threshold_sec)
    monitors = await db.list_monitors(endpoint.id)
    open_incs = await db.get_open_monitor_incidents(endpoint.id)
    offline = await db.get_open_offline_incident(endpoint.id)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    history = await db.list_incidents(endpoint.id, since, limit=50)

    open_list = []
    for inc in open_incs:
        started = parse_iso(inc.started_at)
        dur = (
            int((datetime.now(timezone.utc) - started).total_seconds())
            if started
            else None
        )
        open_list.append(
            {
                "monitor_name": inc.monitor_name or inc.monitor_key,
                "started_at": fmt_ts(inc.started_at),
                "duration": format_duration(dur),
            }
        )

    history_list = []
    for inc in history:
        if inc.ended_at and inc.duration_sec is not None:
            dur = format_duration(inc.duration_sec)
            state = "closed"
        else:
            started = parse_iso(inc.started_at)
            dur = format_duration(
                int((datetime.now(timezone.utc) - started).total_seconds())
                if started
                else None
            )
            state = "open"
        history_list.append(
            {
                "monitor_name": inc.monitor_name or inc.monitor_key,
                "started_at": fmt_ts(inc.started_at),
                "ended_at": fmt_ts(inc.ended_at),
                "duration": dur,
                "state": state,
            }
        )

    return {
        "id": endpoint.id,
        "name": endpoint.name,
        "hostname": endpoint.hostname,
        "last_seen_at": endpoint.last_seen_at,
        "last_seen_label": fmt_ts(endpoint.last_seen_at),
        "status": status,
        "alerts_enabled": endpoint.alerts_enabled,
        "agent_offline": (
            {
                "started_at": fmt_ts(offline.started_at),
            }
            if offline
            else None
        ),
        "monitors": [
            {
                "name": m.name or m.monitor_key,
                "key": m.monitor_key,
                "is_connected": m.is_connected,
                "last_seen_label": fmt_ts(m.last_seen_at),
            }
            for m in monitors
        ],
        "open_incidents": open_list,
        "history_days": days,
        "history": history_list,
    }


@web_router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> Any:
    if is_authenticated(request):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": None},
    )


@web_router.post("/login")
async def login_submit(
    request: Request,
    password: str = Form(...),
    settings: Settings = Depends(get_app_settings),
) -> Any:
    if password == web_password(settings):
        request.session["web_auth"] = True
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Неверный пароль"},
        status_code=401,
    )


@web_router.post("/logout")
async def logout(request: Request) -> Any:
    request.session.clear()
    return RedirectResponse("/login", status_code=302)


@web_router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> Any:
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("index.html", {"request": request})


@web_router.get("/api/web/overview")
async def api_overview(
    request: Request,
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
    _: None = Depends(require_web_auth),
) -> JSONResponse:
    data = await build_overview(db, settings)
    return JSONResponse(data)


@web_router.get("/api/web/endpoints/{endpoint_id}")
async def api_endpoint_detail(
    endpoint_id: int,
    request: Request,
    days: int = 7,
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
    _: None = Depends(require_web_auth),
) -> JSONResponse:
    ep = await db.get_endpoint(endpoint_id)
    if ep is None:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    days = max(1, min(days, 90))
    data = await build_endpoint_detail(db, settings, ep, days=days)
    return JSONResponse(data)


@web_router.post("/api/web/endpoints/{endpoint_id}/alerts")
async def api_toggle_alerts(
    endpoint_id: int,
    request: Request,
    db: Database = Depends(get_db),
    _: None = Depends(require_web_auth),
) -> JSONResponse:
    ep = await db.get_endpoint(endpoint_id)
    if ep is None:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    updated = await db.set_alerts_enabled(endpoint_id, not ep.alerts_enabled)
    assert updated is not None
    return JSONResponse(
        {"id": updated.id, "alerts_enabled": updated.alerts_enabled}
    )


@web_router.delete("/api/web/endpoints/{endpoint_id}")
async def api_delete_endpoint(
    endpoint_id: int,
    request: Request,
    db: Database = Depends(get_db),
    _: None = Depends(require_web_auth),
) -> JSONResponse:
    ep = await db.get_endpoint(endpoint_id)
    if ep is None:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    try:
        ok = await db.delete_endpoint(endpoint_id)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Delete failed: {exc}"
        ) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    return JSONResponse({"ok": True, "id": endpoint_id, "name": ep.name})


def mount_web(app: Any, settings: Settings) -> None:
    from starlette.middleware.sessions import SessionMiddleware

    secret = settings.web_session_secret or f"web:{settings.admin_api_key}"
    app.add_middleware(
        SessionMiddleware,
        secret_key=secret,
        session_cookie="monitor_web_session",
        same_site="lax",
        https_only=False,
        max_age=60 * 60 * 24 * 14,
    )
    static_dir = BASE_DIR / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    app.include_router(web_router)
