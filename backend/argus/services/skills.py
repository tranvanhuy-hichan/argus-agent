"""Doc, kiem tra dieu kien, cai dat skill theo dinh dang SKILL.md cua ClawHub (frontmatter + metadata)."""
import io
import json
import os
import shutil
import stat
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..core.config import Config

META_KEYS = ("openclaw", "clawdbot", "clawdis")  # cac ten khoa metadata ma skill tren ClawHub dang dung (can doc het de tuong thich)
MAX_DEPTH = 6
MAX_ZIP_FILES, MAX_ZIP_BYTES = 500, 20 * 1024 * 1024
OS_ALIAS = {"darwin": "darwin", "macos": "darwin", "linux": "linux", "win32": "win32", "windows": "win32"}


class SkillError(Exception):
    pass


def split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("\n---", 1)
    if len(parts) < 2:
        return {}, text
    head, body = parts[0][3:], parts[1].lstrip("-").lstrip("\n")
    try:
        front = yaml.safe_load(head) or {}
    except yaml.YAMLError:
        front = {}
        for line in head.strip().splitlines():
            k, _, v = line.partition(":")
            if k.strip():
                front[k.strip()] = v.strip()
    if not isinstance(front, dict):
        front = {}
    meta = front.get("metadata")
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            try:
                meta = yaml.safe_load(meta)
            except yaml.YAMLError:
                meta = {}
    front["metadata"] = meta if isinstance(meta, dict) else {}
    return front, body


@dataclass
class Skill:
    name: str
    description: str
    path: Path
    body: str
    front: dict
    meta: dict
    enabled: bool = True
    missing: list[str] = field(default_factory=list)
    origin: dict | None = None

    @property
    def eligible(self) -> bool:
        return not self.missing

    @property
    def active(self) -> bool:
        return self.enabled and self.eligible

    def instructions(self) -> str:
        return self.body.replace("{baseDir}", str(self.path))

    def to_dict(self) -> dict:
        return {
            "name": self.name, "description": self.description, "path": str(self.path),
            "enabled": self.enabled, "eligible": self.eligible, "missing": self.missing,
            "emoji": self.meta.get("emoji") or "", "homepage": self.front.get("homepage") or "",
            "primary_env": self.meta.get("primaryEnv") or "", "origin": self.origin,
            "requires": self.meta.get("requires") or {},
            "model_invocable": not self.front.get("disable-model-invocation", False),
        }


def _gate(meta: dict, cfg: Config, name: str) -> list[str]:
    entry = cfg.skills.get(name)
    missing: list[str] = []
    oses = meta.get("os")
    if oses:
        oses = [oses] if isinstance(oses, str) else oses
        if sys.platform.replace("linux2", "linux") not in {OS_ALIAS.get(o.lower(), o) for o in oses}:
            return [f"os:{'/'.join(oses)}"]
    if meta.get("always"):
        return []
    req = meta.get("requires") or {}
    missing += [f"bin:{b}" for b in req.get("bins", []) if not shutil.which(b)]
    any_bins = req.get("anyBins", [])
    if any_bins and not any(shutil.which(b) for b in any_bins):
        missing.append("anyBin:" + "|".join(any_bins))
    for var in req.get("env", []):
        provided = var in os.environ or (entry and (entry.env.get(var) or (meta.get("primaryEnv") == var and entry.api_key)))
        if not provided:
            missing.append(f"env:{var}")
    missing += [f"config:{c}" for c in req.get("config", [])]  # khong the dap ung (cau hinh rieng cua ung dung khac, Argus khong co)
    return missing


def _find_skill_dirs(root: Path, depth: int = 0):
    if not root.is_dir() or depth > MAX_DEPTH:
        return
    if (root / "SKILL.md").is_file():
        yield root
        return
    for child in sorted(root.iterdir()):
        if child.is_dir() and not child.name.startswith("."):
            yield from _find_skill_dirs(child, depth + 1)


def load_one(d: Path, cfg: Config) -> Skill:
    front, body = split_frontmatter((d / "SKILL.md").read_text(errors="replace"))
    meta = next((front["metadata"][k] for k in META_KEYS if isinstance(front["metadata"].get(k), dict)), {})
    name = str(front.get("name") or d.name)
    entry = cfg.skills.get(name)
    origin = None
    if (d / ".clawhub" / "origin.json").is_file():
        try:
            origin = json.loads((d / ".clawhub" / "origin.json").read_text())
        except json.JSONDecodeError:
            pass
    return Skill(name=name, description=str(front.get("description") or "").strip(), path=d, body=body.strip(), front=front, meta=meta,
                 enabled=entry.enabled if entry else True, missing=_gate(meta, cfg, name), origin=origin)


def discover(cfg: Config) -> dict[str, Skill]:
    skills: dict[str, Skill] = {}
    for d in _find_skill_dirs(cfg.workspace_path() / "skills"):
        try:
            s = load_one(d, cfg)
        except OSError:
            continue
        skills.setdefault(s.name, s)
    return skills


def env_for(skills: dict[str, Skill], cfg: Config) -> dict[str, str]:
    """Bien moi truong skill khai bao, chi cua skill dang bat va du dieu kien."""
    env: dict[str, str] = {}
    for s in skills.values():
        entry = cfg.skills.get(s.name)
        if s.active and entry:
            env.update({k: v for k, v in entry.env.items() if v})
            if s.meta.get("primaryEnv") and entry.api_key:
                env[s.meta["primaryEnv"]] = entry.api_key
    return env


def prompt_block(skills: dict[str, Skill], limit: int = 6000) -> str:
    items = [s for s in skills.values() if s.active and not s.front.get("disable-model-invocation")]
    if not items:
        return ""
    lines, size = [], 0
    for s in items:
        line = f"  <skill><name>{s.name}</name><description>{s.description[:200]}</description></skill>"
        if size + len(line) > limit:
            lines.append("  <!-- con nhieu skill khac bi luoc bot do gioi han prompt -->")
            break
        lines.append(line)
        size += len(line)
    return ("Skills la cac goi huong dan chuyen biet. Neu yeu cau cua nguoi dung khop ro rang voi MOT skill, "
            "hay goi tool skills_read de nap huong dan. SAU KHI doc xong, hay THUC HIEN huong dan do bang tool (vd. chay lenh bang exec) "
            "roi tra loi nguoi dung dua tren KET QUA that, khong tu bia. Huong dan co the nhac ten tool khac "
            "(exec, read, write, web_fetch) - dung tool tuong ung dang co.\n<available_skills>\n" + "\n".join(lines) + "\n</available_skills>")


# ---------- cai dat / go bo
def _safe_extract(data: bytes, dest: Path) -> None:
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise SkillError("file tải về không phải zip hợp lệ") from e
    infos = [i for i in z.infolist() if not i.is_dir()]
    if len(infos) > MAX_ZIP_FILES or sum(i.file_size for i in infos) > MAX_ZIP_BYTES:
        raise SkillError("skill quá lớn (tối đa 500 file / 20MB)")
    names = [i.filename for i in infos]
    prefix = ""
    if "SKILL.md" not in names:
        tops = {n.split("/", 1)[0] for n in names}
        if len(tops) == 1 and f"{next(iter(tops))}/SKILL.md" in names:
            prefix = next(iter(tops)) + "/"
        else:
            raise SkillError("zip không có SKILL.md")
    root = dest.resolve()
    for i in infos:
        rel = i.filename[len(prefix):]
        target = (dest / rel).resolve()
        if root not in target.parents:  # chong zip-slip
            raise SkillError(f"đường dẫn nguy hiểm trong zip: {i.filename}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(z.read(i))
        if target.read_bytes()[:2] == b"#!":
            target.chmod(target.stat().st_mode | stat.S_IXUSR)


def install_zip(cfg: Config, data: bytes, slug: str, origin: dict) -> Skill:
    skills_dir = cfg.workspace_path() / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    target = skills_dir / slug
    if target.exists() and not origin.get("overwrite"):
        prev = (target / ".clawhub" / "origin.json")
        owner = json.loads(prev.read_text()).get("owner") if prev.is_file() else None
        if owner != origin.get("owner"):
            raise SkillError(f"đã có skill '{slug}' (không cùng tác giả). Xóa nó trước khi cài.")
    tmp = Path(tempfile.mkdtemp(prefix=".install-", dir=skills_dir))
    try:
        _safe_extract(data, tmp)
        (tmp / ".clawhub").mkdir(exist_ok=True)
        (tmp / ".clawhub" / "origin.json").write_text(json.dumps({**{k: v for k, v in origin.items() if k != "overwrite"}, "installedAt": int(time.time() * 1000)}))
        if target.exists():
            shutil.rmtree(target)
        tmp.rename(target)
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return load_one(target, cfg)


def remove(cfg: Config, name: str) -> None:
    skills_dir = (cfg.workspace_path() / "skills").resolve()
    s = discover(cfg).get(name)
    if not s:
        raise SkillError(f"không có skill '{name}'")
    path = s.path.resolve()
    if skills_dir not in path.parents:
        raise SkillError("chỉ xóa được skill nằm trong workspace/skills")
    shutil.rmtree(path)


def create(cfg: Config, name: str, description: str, body: str) -> Skill:
    d = cfg.workspace_path() / "skills" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {json.dumps(description, ensure_ascii=False)}\n---\n{body}\n")
    return load_one(d, cfg)
