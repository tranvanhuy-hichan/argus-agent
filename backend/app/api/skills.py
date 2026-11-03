import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core import config as cfgmod
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


@router.get("/skills/{name}")
def get_skill(name: str):
    s = skillmod.discover(cfgmod.load()).get(name)
    if not s:
        raise HTTPException(404, "khong co skill")
    files = sorted(str(p.relative_to(s.path)) for p in s.path.rglob("*") if p.is_file() and ".clawhub" not in p.parts)
    return {**s.to_dict(), "body": s.body, "files": files}


class CreateSkill(BaseModel):
    name: str
    description: str
    body: str


@router.post("/skills")
def create_skill(b: CreateSkill):
    if not NAME_RE.match(b.name):
        raise HTTPException(400, "ten chi gom a-z, 0-9, - va _")
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
    cfg = cfgmod.load()
    hub = ClawHub(cfg.clawhub_url)
    detail = _hub_call(hub.detail, b.slug, b.owner)
    mod = detail.get("moderation") or {}
    if mod.get("isMalwareBlocked") or not detail["installable"]:
        raise HTTPException(403, "ClawHub danh dau skill nay khong an toan de cai")
    data = _hub_call(hub.download, b.slug, b.owner, b.version)
    try:
        skill = skillmod.install_zip(cfg, data, b.slug, {"source": "clawhub", "slug": b.slug, "owner": b.owner,
                                                         "version": b.version or detail.get("version"), "overwrite": b.overwrite})
    except skillmod.SkillError as e:
        raise HTTPException(400, str(e)) from e
    return {"skill": skill.to_dict(), "suspicious": bool(mod.get("isSuspicious"))}
