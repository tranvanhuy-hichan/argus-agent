import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core import config as cfgmod
from ..services import hub_install as hub_install_service
from ..services import skills as skillmod
from ..services.clawhub import ClawHub, ClawHubError

router = APIRouter()
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,60}$")


def _hub() -> ClawHub:
    return ClawHub(cfgmod.load().clawhub_url)


def _hub_call(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except ClawHubError as e:
        raise HTTPException(e.status if e.status in (404, 409, 410, 429) else 502, str(e)) from e


# ---------- skill da cai
@router.get("/skills")
def list_skills():
    cfg = cfgmod.load()
    return [s.to_dict() for s in sorted(skillmod.discover(cfg).values(), key=lambda s: s.name)]


@router.get("/skills/updates")
def skill_updates():
    """So sanh phien ban skill da cai tu ClawHub voi ban moi nhat."""
    hub, out = _hub(), []
    for s in skillmod.discover(cfgmod.load()).values():
        o = s.origin
        if not o or o.get("source") != "clawhub":
            continue
        try:
            latest = hub.detail(o["slug"], o["owner"]).get("version")
        except ClawHubError:
            continue
        if latest and latest != o.get("version"):
            out.append({"name": s.name, "current": o.get("version"), "latest": latest})
    return out


@router.post("/skills/{name}/update")
def skill_update(name: str):
    cfg = cfgmod.load()
    s = skillmod.discover(cfg).get(name)
    if not s or not s.origin or s.origin.get("source") != "clawhub":
        raise HTTPException(400, "chỉ cập nhật được skill cài từ ClawHub")
    hub = ClawHub(cfg.clawhub_url)
    detail = _hub_call(hub.detail, s.origin["slug"], s.origin["owner"])
    if (detail.get("moderation") or {}).get("isMalwareBlocked") or not detail["installable"]:
        raise HTTPException(403, "ClawHub đánh dấu phiên bản mới là không an toàn")
    data = _hub_call(hub.download, s.origin["slug"], s.origin["owner"], None)
    try:
        new = skillmod.install_zip(cfg, data, s.origin["slug"], {"source": "clawhub", "slug": s.origin["slug"], "owner": s.origin["owner"],
                                                                "version": detail.get("version"), "overwrite": True})
    except skillmod.SkillError as e:
        raise HTTPException(400, str(e)) from e
    return new.to_dict()


@router.get("/skills/{name}")
def get_skill(name: str):
    s = skillmod.discover(cfgmod.load()).get(name)
    if not s:
        raise HTTPException(404, "không có skill")
    files = sorted(str(p.relative_to(s.path)) for p in s.path.rglob("*") if p.is_file() and ".clawhub" not in p.parts)
    return {**s.to_dict(), "body": s.body, "files": files}


class CreateSkill(BaseModel):
    name: str
    description: str
    body: str


@router.post("/skills")
def create_skill(b: CreateSkill):
    if not NAME_RE.match(b.name):
        raise HTTPException(400, "tên chỉ gồm a-z, 0-9, - và _")
    return skillmod.create(cfgmod.load(), b.name, b.description, b.body).to_dict()


@router.put("/skills/{name}/config")
def configure_skill(name: str, entry: cfgmod.SkillEntry):
    cfg = cfgmod.load()
    entry = cfgmod.merge_secrets(cfgmod.Config(providers=cfg.providers, skills={name: entry}), cfg).skills[name]
    cfg.skills[name] = entry
    cfgmod.save(cfg)
    return {"ok": True}


@router.delete("/skills/{name}")
def delete_skill(name: str):
    try:
        skillmod.remove(cfgmod.load(), name)
    except skillmod.SkillError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True}


# ---------- ClawHub
@router.get("/clawhub/tools")
def skill_tools():
    from ..services import skill_picks
    return skill_picks.TOOLS


@router.get("/clawhub/picks")
def hub_picks():
    from ..services import skill_picks
    return skill_picks.picks(_hub())


@router.get("/clawhub/search")
def hub_search(q: str):
    return _hub_call(_hub().search, q)


@router.get("/clawhub/browse")
def hub_browse(sort: str = "downloads", cursor: str | None = None):
    return _hub_call(_hub().browse, sort, cursor)


@router.get("/clawhub/skill")
def hub_detail(slug: str, owner: str):
    hub = _hub()
    detail = _hub_call(hub.detail, slug, owner)
    try:
        detail["skill_md"] = hub.preview(slug, owner)[:20000]
    except ClawHubError:
        detail["skill_md"] = None
    return detail


class InstallBody(BaseModel):
    slug: str
    owner: str
    version: str | None = None
    overwrite: bool = False


@router.post("/clawhub/install")
def hub_install(b: InstallBody):
    try:
        skill, suspicious = hub_install_service.install(cfgmod.load(), b.slug, b.owner, b.version, b.overwrite)
    except hub_install_service.BlockedError as e:
        raise HTTPException(403, str(e)) from e
    except skillmod.SkillError as e:
        raise HTTPException(400, str(e)) from e
    except ClawHubError as e:
        raise HTTPException(e.status if e.status in (404, 409, 410, 429) else 502, str(e)) from e
    return {"skill": skill.to_dict(), "suspicious": suspicious}
