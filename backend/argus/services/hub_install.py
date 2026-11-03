"""Cai/cap nhat skill tu ClawHub; dung chung cho API web va CLI."""
from ..core.config import Config
from . import skills as skillmod
from .clawhub import ClawHub


class BlockedError(skillmod.SkillError):
    """ClawHub danh dau skill la khong an toan."""


def install(cfg: Config, slug: str, owner: str, version: str | None = None, overwrite: bool = False) -> tuple[skillmod.Skill, bool]:
    """Tra ve (skill, bi_gan_co_dang_ngo). Nem ClawHubError / SkillError."""
    hub = ClawHub(cfg.clawhub_url)
    detail = hub.detail(slug, owner)
    mod = detail.get("moderation") or {}
    if mod.get("isMalwareBlocked") or not detail["installable"]:
        raise BlockedError("ClawHub đánh dấu skill này không an toàn để cài")
    data = hub.download(slug, owner, version)
    skill = skillmod.install_zip(cfg, data, slug, {"source": "clawhub", "slug": slug, "owner": owner, "version": version or detail.get("version"), "overwrite": overwrite})
    return skill, bool(mod.get("isSuspicious"))
