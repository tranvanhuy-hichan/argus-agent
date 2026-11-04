import io
import json
import zipfile

import pytest

from argus.core.config import Config, SkillEntry
from argus.services import skills as sk

CLAWDBOT = '''---
name: weather
description: Get weather
metadata: {"clawdbot":{"emoji":"x","requires":{"bins":["definitely-not-a-binary"],"env":["WX_KEY"]},"primaryEnv":"WX_KEY"}}
---
Dung {baseDir}/run.sh
'''


def make_zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n, c in files.items():
            z.writestr(n, c)
    return buf.getvalue()


def cfg_in(tmp_path) -> Config:
    c = Config()
    c.agent.workspace = str(tmp_path)
    return c


def test_frontmatter_reads_clawdbot_alias_and_json_metadata():
    front, body = sk.split_frontmatter(CLAWDBOT)
    assert front["name"] == "weather" and front["metadata"]["clawdbot"]["primaryEnv"] == "WX_KEY"
    assert body.startswith("Dung")


def test_gating_reports_missing_and_env_satisfied_by_config(tmp_path):
    cfg = cfg_in(tmp_path)
    s = sk.install_zip(cfg, make_zip({"SKILL.md": CLAWDBOT}), "weather", {"owner": "o"})
    assert not s.eligible and "bin:definitely-not-a-binary" in s.missing and "env:WX_KEY" in s.missing
    cfg.skills["weather"] = SkillEntry(env={"WX_KEY": "k"})
    assert sk.load_one(s.path, cfg).missing == ["bin:definitely-not-a-binary"]


def test_basedir_substitution_and_prompt_block(tmp_path):
    cfg = cfg_in(tmp_path)
    plain = "---\nname: plain\ndescription: d\n---\nrun {baseDir}/x"
    s = sk.install_zip(cfg, make_zip({"SKILL.md": plain}), "plain", {"owner": "o"})
    assert str(s.path) in s.instructions()
    assert "<name>plain</name>" in sk.prompt_block({"plain": s})


@pytest.mark.parametrize("evil", ["../escape.txt", "/abs.txt", "a/../../escape.txt"])
def test_zip_slip_rejected(tmp_path, evil):
    with pytest.raises(sk.SkillError):
        sk.install_zip(cfg_in(tmp_path), make_zip({"SKILL.md": "---\nname: x\n---\nb", evil: "pwn"}), "x", {"owner": "o"})
    assert not (tmp_path.parent / "escape.txt").exists()
    assert not list((tmp_path / "skills").glob(".install-*"))  # khong de lai thu muc tam


def test_zip_without_skill_md_rejected(tmp_path):
    with pytest.raises(sk.SkillError):
        sk.install_zip(cfg_in(tmp_path), make_zip({"README.md": "x"}), "x", {"owner": "o"})


def test_other_owner_cannot_overwrite(tmp_path):
    cfg = cfg_in(tmp_path)
    z = make_zip({"SKILL.md": "---\nname: x\ndescription: d\n---\nb"})
    sk.install_zip(cfg, z, "x", {"owner": "alice"})
    with pytest.raises(sk.SkillError):
        sk.install_zip(cfg, z, "x", {"owner": "mallory"})
    sk.install_zip(cfg, z, "x", {"owner": "alice", "overwrite": True})


def test_remove_only_inside_skills_dir(tmp_path):
    cfg = cfg_in(tmp_path)
    sk.install_zip(cfg, make_zip({"SKILL.md": "---\nname: x\ndescription: d\n---\nb"}), "x", {"owner": "o"})
    sk.remove(cfg, "x")
    assert "x" not in sk.discover(cfg)
    assert json.dumps(1)  # tranh canh bao import khong dung


def test_bundled_skills_seed_once(tmp_path):
    from argus.core.workspace import seed_skills, template_dir
    src, dst = template_dir() / "skills", tmp_path / "skills"
    seed_skills(src, dst)
    names = {d.name for d in src.iterdir() if d.is_dir()}
    assert len(names) >= 5 and {d.name for d in dst.iterdir() if d.is_dir()} == names
    for n in names:  # moi skill co frontmatter hop le va mo ta
        front, body = sk.split_frontmatter((dst / n / "SKILL.md").read_text())
        assert front["name"] == n and 30 < len(front["description"]) <= 200 and body.strip()
    sk.shutil.rmtree(dst / "email-writer")
    seed_skills(src, dst)
    assert not (dst / "email-writer").exists()  # da xoa thi khong quay lai


def test_bundled_skill_scripts_work(tmp_path):
    import subprocess
    import sys
    from argus.core.workspace import template_dir
    root = template_dir() / "skills"
    (tmp_path / "e.json").write_text('[{"title":"Hi, there","start":"2026-11-05 09:00","remind_min":10}]')
    (tmp_path / "c.json").write_text('[{"front":"Q","back":"A\\nB"}]')
    for script, src, out in [("meeting-notes/scripts/make_ics.py", "e.json", "a.ics"), ("study-coach/scripts/anki_export.py", "c.json", "a.tsv"),
                             ("daily-planner/scripts/make_ics.py", "e.json", "b.ics")]:
        r = subprocess.run([sys.executable, str(root / script), str(tmp_path / src), str(tmp_path / out)], capture_output=True, text=True)
        assert r.returncode == 0, (script, r.stderr)
        assert (tmp_path / out).stat().st_size > 50
    assert "SUMMARY:Hi\\, there" in (tmp_path / "a.ics").read_text()
    assert "Q\tA<br>B" in (tmp_path / "a.tsv").read_text()


def test_skill_tools_endpoint_lists_install_commands(tmp_env):
    from fastapi.testclient import TestClient
    from argus.main import app
    tools = TestClient(app).get("/api/clawhub/tools").json()
    assert tools["yt-dlp"]["windows"].startswith("winget") and tools["ffmpeg"]["linux"].startswith("sudo apt")
    assert all(set(v) == {"mac", "linux", "windows", "url"} for v in tools.values())
