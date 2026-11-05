from argus.services import agent, commands


def test_expand_commands():
    assert "git diff HEAD" in commands.expand("/review")
    out = commands.expand("/plan thêm đăng nhập Google")
    assert out.startswith(commands.COMMANDS["plan"]) and out.endswith("thêm đăng nhập Google")
    assert commands.expand("/unknown x") is None and commands.expand("review") is None and commands.expand("/skill-name") is None


def test_augment_expands_command_but_keeps_plain_text(tmp_path):
    assert "KHÔNG sửa" in agent._augment({"role": "user", "content": "/review"}, tmp_path)["content"]
    plain = {"role": "user", "content": "xin chào", "_id": 3}
    assert agent._augment(plain, tmp_path) == {"role": "user", "content": "xin chào"}


def test_at_mentions_resolve_only_real_inside_paths(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x")
    out = agent._augment({"role": "user", "content": "sửa @src/app.py và xem @src, hỏi @notion hay @../etc/passwd và email a@b.com"}, tmp_path)["content"]
    assert "src/app.py, src/" in out and "notion" not in out.split("[Người dùng")[1] and "passwd" not in out.split("[Người dùng")[1] and "b.com" not in out.split("[Người dùng")[1]
