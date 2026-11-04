from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services import habits
from ..services.scheduler import ScheduleError

AUTO = True
router = APIRouter()


class Draft(BaseModel):
    kind: str = "skill"
    name: str
    title: str = ""
    description: str = ""
    body: str = ""
    prompt: str = ""
    schedule: str = ""


@router.get("/habits")
def list_habits():
    return habits.list_pending()


@router.post("/habits/{sid}/accept")
def accept(sid: str, d: Draft):
    try:
        return habits.accept(sid, d.model_dump())
    except (ValueError, ScheduleError) as e:
        raise HTTPException(400, str(e)) from e


@router.post("/habits/{sid}/dismiss")
def dismiss(sid: str):
    if not habits.dismiss(sid):
        raise HTTPException(404, "không có gợi ý này")
    return {"ok": True}
