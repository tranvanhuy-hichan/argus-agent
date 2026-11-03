"""argus skills list|search|install|remove|update: quan ly skill (ClawHub) tu dong lenh."""
import json

from ..core import config as cfgmod
from ..services import hub_install
from ..services import skills as skillmod
from ..services.clawhub import ClawHub, ClawHubError
from . import runtime
from .ui import L, bad, bold, cyan, dim, err, green, interactive, ask, ask_yes_no, choose, ok, warn, yellow


def _fmt_status(s: skillmod.Skill) -> str:
    if not s.enabled:
        return dim(L("tắt", "off"))
    return green(L("sẵn sàng", "ready")) if s.eligible else yellow(L("cần thiết lập", "needs setup"))


def list_(as_json: bool) -> int:
    cfg = runtime.bootstrap()
    skills = sorted(skillmod.discover(cfg).values(), key=lambda s: s.name)
    if as_json:
        print(json.dumps([s.to_dict() for s in skills], ensure_ascii=False, indent=2))
        return 0
    if not skills:
        print(dim(L("Chưa có skill. Tìm bằng: argus skills search <từ khóa>", "No skills yet. Find some with: argus skills search <keyword>")))
        return 0
    for s in skills:
        origin = f"{s.origin['owner']}/{s.origin['slug']}" + (f" v{s.origin['version']}" if s.origin.get("version") else "") if s.origin else dim(L("tự tạo", "local"))
        print(f"{bold(s.name):28}{_fmt_status(s):24}{origin}")
        if not s.eligible:
            print(dim("    " + ", ".join(s.missing)))
    return 0


def search(query: str, limit: int, as_json: bool) -> int:
    cfg = runtime.bootstrap()
    try:
        rows = ClawHub(cfg.clawhub_url).search(query, limit)
    except ClawHubError as e:
        err(str(e))
        return 1
    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    if not rows:
        print(dim(L("Không tìm thấy skill nào.", "No skills found.")))
        return 0
    for r in rows:
        print(f"{cyan(r['owner'] + '/' + r['slug'])}  {dim('↓' + str(r['downloads']))}  {'★' if r['official'] else ''}")
        print(f"    {r['summary'][:110]}")
    print(dim(L("\nCài đặt: argus skills install <owner>/<slug>", "\nInstall: argus skills install <owner>/<slug>")))
    return 0


def resolve(hub: ClawHub, ref: str) -> tuple[str, str] | None:
    """'@owner/slug', 'owner/slug' hoac 'slug' (tim tren ClawHub; neu trung ten thi hoi chon)."""
    ref = ref.lstrip("@")
    if "/" in ref:
        owner, slug = ref.split("/", 1)
        return slug, owner
    matches = [r for r in hub.search(ref, 24) if r["slug"] == ref]
    if not matches:
        err(L(f"Không tìm thấy skill '{ref}'. Thử: argus skills search {ref}", f"No skill '{ref}' found. Try: argus skills search {ref}"))
        return None
    if len(matches) == 1:
        return matches[0]["slug"], matches[0]["owner"]
    if not interactive():
        err(L(f"Có {len(matches)} skill trùng tên '{ref}', hãy chỉ rõ <owner>/<slug>: " + ", ".join(m["owner"] for m in matches),
              f"{len(matches)} skills share the name '{ref}', specify <owner>/<slug>: " + ", ".join(m["owner"] for m in matches)))
        return None
    i = choose(L("Chọn", "Choose"), [f"{m['owner']}/{m['slug']}  ({m['downloads']}↓)  {m['summary'][:60]}" for m in matches])
    return matches[i]["slug"], matches[i]["owner"]


def install(ref: str, yes: bool, overwrite: bool) -> int:
    cfg = runtime.bootstrap()
    hub = ClawHub(cfg.clawhub_url)
    try:
        target = resolve(hub, ref)
        if not target:
            return 1
        slug, owner = target
        detail = hub.detail(slug, owner)
        mod = detail.get("moderation") or {}
        print(f"{bold(owner + '/' + slug)}  v{detail.get('version')}  ↓{detail['downloads']}")
        print(f"  {detail['summary']}")
        if mod.get("isSuspicious"):
            warn(L("ClawHub gắn cờ skill này là đáng ngờ: " + str(mod.get("summary", "")), "ClawHub flagged this skill as suspicious: " + str(mod.get("summary", ""))))
        if not yes:
            if not interactive():
                err(L("Cần --yes khi chạy không tương tác (hãy đọc SKILL.md trước).", "--yes is required in non-interactive mode (read SKILL.md first)."))
                return 1
            try:
                head = hub.preview(slug, owner).splitlines()[:18]
                print(dim("  ┌─ SKILL.md\n" + "\n".join("  │ " + line for line in head)))
            except ClawHubError:
                pass
            print(yellow(L("  Skill là hướng dẫn mà agent sẽ làm theo, có thể bảo agent chạy lệnh. Lệnh shell vẫn cần bạn xác nhận.",
                           "  A skill is a set of instructions the agent will follow and may tell it to run commands. Shell commands still need your approval.")))
            if not ask_yes_no(L("Cài đặt skill này?", "Install this skill?"), False):
                return 1
        skill, suspicious = hub_install.install(cfg, slug, owner, overwrite=overwrite)
    except hub_install.BlockedError as e:
        bad(str(e))
        return 1
    except (skillmod.SkillError, ClawHubError) as e:
        err(str(e))
        return 1
    ok(L(f"Đã cài {bold(skill.name)}", f"Installed {bold(skill.name)}") + (dim(L("  (cần thiết lập: ", "  (needs setup: ") + ", ".join(skill.missing) + ")") if skill.missing else ""))
    return 0


def remove(name: str, yes: bool) -> int:
    cfg = runtime.bootstrap()
    if name not in skillmod.discover(cfg):
        err(L(f"Không có skill '{name}'.", f"No skill '{name}'."))
        return 1
    if not yes and not (interactive() and ask_yes_no(L(f"Xóa skill '{name}'?", f"Delete skill '{name}'?"), False)):
        return 1
    skillmod.remove(cfg, name)
    ok(L("Đã xóa.", "Removed."))
    return 0


def update(name: str | None) -> int:
    cfg = runtime.bootstrap()
    hub = ClawHub(cfg.clawhub_url)
    code = 0
    found = False
    for s in skillmod.discover(cfg).values():
        o = s.origin
        if not o or o.get("source") != "clawhub" or (name and s.name != name):
            continue
        found = True
        try:
            latest = hub.detail(o["slug"], o["owner"]).get("version")
            if latest == o.get("version"):
                print(dim(f"{s.name}: {L('đã mới nhất', 'up to date')} (v{latest})"))
                continue
            hub_install.install(cfg, o["slug"], o["owner"], overwrite=True)
            ok(f"{s.name}: v{o.get('version')} → v{latest}")
        except (skillmod.SkillError, ClawHubError) as e:
            err(f"{s.name}: {e}")
            code = 1
    if not found:
        print(dim(L("Không có skill nào cài từ ClawHub để cập nhật.", "No ClawHub-installed skills to update.")))
    return code


__all__ = ["list_", "search", "install", "remove", "update", "cfgmod", "ask"]
