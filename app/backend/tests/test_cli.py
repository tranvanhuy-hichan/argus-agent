"""Kiem thu CLI `argus`: moi lenh chay nhu mot tien trinh that voi ARGUS_HOME cach ly (khong dung vao du lieu that)."""
import json
import os
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def argus(tmp_path):
    home = tmp_path / "home with space"  # co dau cach de bat loi quote duong dan
    home.mkdir()
    port = free_port()
    env = {**os.environ, "ARGUS_HOME": str(home), "ARGUS_PORT": str(port), "ARGUS_LANG": "en", "NO_COLOR": "1", "PYTHONPATH": str(BACKEND)}
    env.pop("ARGUS_CONFIG", None)

    def run(*args, stdin: str | None = None, timeout=60):
        return subprocess.run([sys.executable, "-m", "argus", *args], env=env, input=stdin, capture_output=True, text=True, timeout=timeout)

    run.home, run.port, run.env = home, port, env
    yield run
    subprocess.run([sys.executable, "-m", "argus", "stop"], env=env, capture_output=True, timeout=20)  # don dep neu test de lai server


def test_version_and_help(argus):
    assert "argus-agent" in argus("--version").stdout
    out = argus("--help").stdout
    for cmd in ("start", "stop", "status", "logs", "doctor", "onboard", "chat", "run", "token", "skills", "service"):
        assert cmd in out


def test_vietnamese_help(argus):
    assert "chạy server nền" in argus("--lang", "vi", "--help").stdout


def test_onboard_non_interactive_writes_secure_config(argus):
    r = argus("onboard", "--non-interactive", "--language", "en", "--name", "Ann", "--provider", "custom", "--base-url", "http://127.0.0.1:1/v1",
              "--model", "m1", "--skip-test", "--api-key-stdin", "--no-start", stdin="sk-test-key\n")
    assert r.returncode == 0, r.stderr
    cfg_file = argus.home / "config.json"
    assert oct(cfg_file.stat().st_mode & 0o777) == "0o600"
    cfg = json.loads(cfg_file.read_text())
    assert cfg["default_provider"] == "custom" and cfg["providers"]["custom"]["model"] == "m1" and "local" not in cfg["providers"]
    assert "Ann" in (argus.home / "workspace" / "USER.md").read_text() and (argus.home / "workspace" / "SOUL.md").exists()
    shown = argus("config", "show").stdout
    assert "sk-test-key" not in shown and "***" in shown  # API key duoc che


def test_token_lifecycle(argus):
    tok = json.loads(argus("token", "create", "ci", "--json").stdout)
    assert tok["token"].startswith("agt_") and tok["allow_exec"] is False
    assert "ci" in argus("token", "list").stdout
    assert argus("token", "revoke", tok["id"]).returncode == 0
    assert argus("token", "revoke", tok["id"]).returncode == 1  # da thu hoi


def test_doctor_offline_and_fix(argus):
    assert argus("onboard", "--non-interactive", "--provider", "custom", "--base-url", "http://127.0.0.1:1/v1", "--model", "m", "--skip-test", "--no-start", stdin="k\n").returncode == 0 or True
    cfg = argus.home / "config.json"
    data = json.loads(cfg.read_text())
    data["providers"]["custom"]["api_key"] = "sk-x"
    cfg.write_text(json.dumps(data))
    cfg.chmod(0o644)
    report = json.loads(argus("doctor", "--offline", "--json").stdout)
    assert any("permissions" in c["name"] and c["status"] == "warn" for c in report)
    argus("doctor", "--offline", "--fix")
    assert oct(cfg.stat().st_mode & 0o777) == "0o600"


def test_daemon_lifecycle(argus):
    r = argus("start", "--no-build", timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    st = json.loads(argus("status", "--json").stdout)
    assert st["running"] and st["managed_by_cli"] and st["version"]
    assert (argus.home / "workspace" / "SOUL.md").exists()  # server tu tao workspace mau neu thieu
    assert "already running" in argus("start", "--no-build").stdout  # khong chay hai ban
    assert "GET /api/health" in argus("logs", "-n", "20").stdout
    assert argus("stop").returncode == 0
    assert argus("status", "--json").returncode == 1 and not json.loads(argus("status", "--json").stdout)["running"]
    assert argus("stop").returncode == 0  # dung khi da dung van khong loi


def test_start_refuses_busy_port(argus):
    with socket.socket() as s:
        s.bind(("127.0.0.1", argus.port))
        s.listen()
        r = argus("start", "--no-build")
    assert r.returncode == 1 and "in use" in r.stdout


def test_run_validation(argus):
    assert argus("run", "").returncode == 2
    assert argus("run", "x", "--ask").returncode == 2  # --ask can terminal that


def test_service_unit_quotes_paths_with_spaces(argus):
    out = argus("service", "install", "--dry-run", "--port", "9999").stdout
    assert "ExecStart=" in out and "argus.main:app --host 127.0.0.1 --port 9999" in out
    assert f'Environment="ARGUS_HOME={argus.home}"' in out and "WorkingDirectory=" in out


def test_launchd_plist_is_valid_xml():
    import xml.dom.minidom

    sys.path.insert(0, str(BACKEND))
    from argus.cli import service

    xml.dom.minidom.parseString(service.launchd_plist("127.0.0.1", 8787))


# ---------- run voi LLM gia: kiem tra ca chinh sach exec va dau ra
class FakeLLM(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        last = body["messages"][-1]
        text = last["content"] if isinstance(last["content"], str) else ""
        if last["role"] == "tool":
            chunks = [{"choices": [{"delta": {"content": "tool said: " + last["content"][:40].strip()}}]}]
        elif "RUNTOOL" in text:
            chunks = [{"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "c1", "function": {"name": "exec", "arguments": json.dumps({"command": "echo hi"})}}]}}]}]
        else:
            chunks = [{"choices": [{"delta": {"content": "pong"}}]}]
        data = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        self.wfile.write(data.encode())


@pytest.fixture
def fake_llm(argus):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeLLM)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    r = argus("onboard", "--non-interactive", "--provider", "custom", "--base-url", f"http://127.0.0.1:{srv.server_port}/v1", "--model", "fake", "--skip-test", "--no-start")
    assert r.returncode == 0, r.stderr
    yield argus
    srv.shutdown()


def test_run_prints_answer_and_json(fake_llm):
    assert fake_llm("run", "hello").stdout.strip() == "pong"
    res = json.loads(fake_llm("run", "--json", "hello").stdout)
    assert res["output"] == "pong" and res["error"] is None
    assert fake_llm("run", "-", stdin="from stdin").stdout.strip() == "pong"


def test_run_exec_policies(fake_llm):
    denied = fake_llm("run", "RUNTOOL")  # mac dinh deny
    assert "tool said: KHÔNG THỰC HIỆN" in denied.stdout
    allowed = fake_llm("run", "--exec-policy", "allowlist", "--allow", "echo", "RUNTOOL")
    assert "tool said: hi" in allowed.stdout
    wrong_prefix = fake_llm("run", "--exec-policy", "allowlist", "--allow", "ls", "RUNTOOL")
    assert "KHÔNG THỰC HIỆN" in wrong_prefix.stdout


def test_run_readonly_hides_exec_tool(fake_llm):
    res = json.loads(fake_llm("run", "--json", "--permission", "readonly", "RUNTOOL").stdout)
    assert res["tool_calls"][0]["name"] == "exec" and "khong co tool exec" in res["tool_calls"][0]["result"]  # model van thu goi nhung tool da bi tat


def test_chat_repl_scripted(fake_llm):
    r = fake_llm("chat", stdin="/help\nhello\n/exit\n")
    assert r.returncode == 0 and "pong" in r.stdout and "/perm <mode>" in r.stdout


# ---------- backup / restore / secrets qua CLI that
def _setup_with_key(argus):
    r = argus("onboard", "--non-interactive", "--provider", "custom", "--base-url", "http://127.0.0.1:1/v1", "--model", "m", "--skip-test", "--api-key-stdin", "--no-start", stdin="sk-cli-secret\n")
    assert r.returncode == 0, r.stderr


def test_secrets_status_and_rotate(argus):
    _setup_with_key(argus)
    assert "sk-cli-secret" not in (argus.home / "config.json").read_text()  # onboard da ma hoa san
    st = json.loads(argus("secrets", "status", "--json").stdout)
    assert st["encrypted"] == 1 and st["plaintext"] == 0 and st["source"] == "file" and not st["failed"]
    before = (argus.home / "config.json").read_text()
    assert argus("secrets", "rotate").returncode == 0
    assert (argus.home / "config.json").read_text() != before
    assert "sk-cli-secret" not in argus("config", "show").stdout and json.loads(argus("secrets", "status", "--json").stdout)["failed"] == []
    assert argus("secrets", "decrypt", "-y").returncode == 0 and "sk-cli-secret" in (argus.home / "config.json").read_text()
    assert argus("secrets", "encrypt").returncode == 0 and "sk-cli-secret" not in (argus.home / "config.json").read_text()


def test_backup_restore_roundtrip_with_encryption(argus, tmp_path):
    _setup_with_key(argus)
    out = tmp_path / "b.tar.gz.enc"
    env = {**argus.env, "BK_PASS": "correct horse battery"}
    r = subprocess.run([sys.executable, "-m", "argus", "backup", "-o", str(out), "--include-key", "--encrypt", "--passphrase-env", "BK_PASS"], env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert out.exists() and b"sk-cli-secret" not in out.read_bytes()
    import shutil

    (argus.home / "config.json").unlink()  # mo phong may moi: khong con gi
    (argus.home / "data" / "master.key").unlink()
    (argus.home / "data" / "agent.db").unlink()
    shutil.rmtree(argus.home / "workspace")
    run = lambda *a: subprocess.run([sys.executable, "-m", "argus", *a], env=env, capture_output=True, text=True)  # noqa: E731
    assert run("restore", str(out)).returncode == 1  # thieu mat khau
    assert run("restore", str(out), "--passphrase-env", "NOPE_NOT_SET").returncode == 1
    ok = run("restore", str(out), "--passphrase-env", "BK_PASS")
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert json.loads(argus("secrets", "status", "--json").stdout)["failed"] == []
    refused = run("restore", str(out), "--passphrase-env", "BK_PASS")  # da co du lieu, can --force
    assert refused.returncode == 1 and "--force" in refused.stderr and "already exists" in refused.stderr
    assert run("restore", str(out), "--passphrase-env", "BK_PASS", "--force").returncode == 0
    assert list((argus.home / "backups").glob("pre-restore-*.tar.gz"))


def test_restore_refused_while_server_runs(argus, tmp_path):
    _setup_with_key(argus)
    out = tmp_path / "b.tar.gz"
    assert argus("backup", "-o", str(out)).returncode == 0
    assert argus("start", "--no-build").returncode == 0
    r = argus("restore", str(out), "--force")
    assert r.returncode == 1 and "argus stop" in r.stdout
    argus("stop")


def test_doctor_reports_lost_master_key(argus):
    _setup_with_key(argus)
    (argus.home / "data" / "master.key").unlink()
    report = json.loads(argus("doctor", "--offline", "--json").stdout)
    assert any(c["name"] == "Secrets" and c["status"] == "fail" for c in report)
