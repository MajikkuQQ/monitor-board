from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from server.alerts import AlertHub
from server.db import Database


class MonitorPayload(BaseModel):
    key: str = Field(min_length=1, max_length=512)
    name: str = Field(default="", max_length=512)


class HeartbeatRequest(BaseModel):
    hostname: Optional[str] = Field(default=None, max_length=255)
    monitors: list[MonitorPayload] = Field(default_factory=list)


class CreateEndpointRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)


def get_db(request: Request) -> Database:
    return request.app.state.db


def get_alerts(request: Request) -> AlertHub:
    return request.app.state.alerts


def get_admin_key(request: Request) -> str:
    return request.app.state.admin_api_key


async def require_admin(
    x_admin_key: Optional[str] = Header(default=None),
    admin_key: str = Depends(get_admin_key),
) -> None:
    if not x_admin_key or x_admin_key != admin_key:
        raise HTTPException(status_code=401, detail="Invalid admin key")


router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/api/v1/heartbeat")
async def heartbeat(
    body: HeartbeatRequest,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Database = Depends(get_db),
    alerts: AlertHub = Depends(get_alerts),
) -> dict[str, object]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    endpoint = await db.get_endpoint_by_token(token)
    if endpoint is None:
        raise HTTPException(status_code=401, detail="Unknown agent token")

    monitors = [{"key": m.key, "name": m.name or m.key} for m in body.monitors]
    changes = await db.process_heartbeat(endpoint, body.hostname, monitors)
    await alerts.publish_many(changes)
    return {
        "ok": True,
        "endpoint_id": endpoint.id,
        "changes": [c.kind for c in changes],
    }


@router.post("/admin/endpoints", dependencies=[Depends(require_admin)])
async def create_endpoint(
    body: CreateEndpointRequest,
    db: Database = Depends(get_db),
) -> dict[str, object]:
    endpoint = await db.create_endpoint(body.name.strip())
    return {
        "id": endpoint.id,
        "name": endpoint.name,
        "agent_token": endpoint.agent_token,
    }


@router.get("/admin/endpoints", dependencies=[Depends(require_admin)])
async def list_endpoints(db: Database = Depends(get_db)) -> dict[str, object]:
    items = await db.list_endpoints()
    return {
        "endpoints": [
            {
                "id": e.id,
                "name": e.name,
                "hostname": e.hostname,
                "last_seen_at": e.last_seen_at,
                "alerts_enabled": e.alerts_enabled,
            }
            for e in items
        ]
    }
