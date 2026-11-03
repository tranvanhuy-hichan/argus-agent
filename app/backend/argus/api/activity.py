"""Nhat ky hoat dong (audit), hop thu thong bao va tim kiem bo nho."""
from fastapi import APIRouter, Query
from pydantic import BaseModel

from ..services import audit, notifications, sessions

router = APIRouter()


@router.get("/audit")
def audit_list(limit: int = Query(100, le=500), offset: int = 0, tool: str = "", decision: str = "", source: str = ""):
    return audit.list_events(limit, offset, tool, decision, source)


@router.get("/notifications")
def notif_list():
    return {"items": notifications.list_all(), "unread": notifications.unread_count()}


@router.get("/notifications/count")
def notif_count():
    return {"unread": notifications.unread_count()}


class ReadBody(BaseModel):
    ids: list[int] | None = None


@router.post("/notifications/read")
def notif_read(b: ReadBody):
    notifications.mark_read(b.ids)
    return {"ok": True}


@router.delete("/notifications")
def notif_clear():
    notifications.delete_all()
    return {"ok": True}


@router.get("/search")
def search(q: str, limit: int = Query(10, le=30)):
    return sessions.search(q, limit)
