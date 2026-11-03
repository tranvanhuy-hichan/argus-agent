"""argus token create|list|revoke: quan ly API token truc tiep qua co so du lieu (khong can server chay)."""
import json

from ..services import tokens
from . import runtime
from .ui import L, bad, bold, dim, err, fmt_ts, ok, warn, yellow


def create(name: str, allow_exec: bool, as_json: bool) -> int:
    runtime.bootstrap()
    info, token = tokens.create(name, allow_exec)
    if as_json:
        print(json.dumps({**info, "token": token}, ensure_ascii=False))
        return 0
    ok(L("Đã tạo token. Hãy lưu ngay, sẽ không hiện lại lần nữa:", "Token created. Save it now, it will not be shown again:"))
    print(f"\n  {bold(token)}\n")
    print(dim(L("  Dùng: Authorization: Bearer <token> → POST /v1/run  ·  hoặc ARGUS_TOKEN=<token> cho MCP server `agent_run`",
                "  Use: Authorization: Bearer <token> → POST /v1/run  ·  or ARGUS_TOKEN=<token> for the `agent_run` MCP server")))
    if allow_exec:
        warn(L("Token này được phép chạy lệnh (exec_policy allow/allowlist). Chỉ đưa cho ứng dụng bạn tin tưởng.", "This token may run commands (exec_policy allow/allowlist). Only give it to apps you trust."))
    return 0


def list_tokens(as_json: bool) -> int:
    runtime.bootstrap()
    rows = tokens.list_all()
    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    if not rows:
        print(dim(L("Chưa có token nào. Tạo bằng: argus token create <tên>", "No tokens yet. Create one with: argus token create <name>")))
        return 0
    print(dim(f"{'ID':10}{L('TÊN', 'NAME'):24}{'PREFIX':14}{L('QUYỀN', 'SCOPE'):12}{L('DÙNG LẦN CUỐI', 'LAST USED')}"))
    for t in rows:
        scope = yellow("exec") if t["allow_exec"] else "read"
        print(f"{t['id']:10}{t['name'][:22]:24}{t['prefix']:14}{scope:12}{fmt_ts(t['last_used']) if t['last_used'] else dim('—')}")
    return 0


def revoke(token_id: str) -> int:
    runtime.bootstrap()
    if not any(t["id"] == token_id for t in tokens.list_all()):
        bad(L(f"Không có token '{token_id}'. Xem danh sách: argus token list", f"No token '{token_id}'. List them with: argus token list"))
        return 1
    tokens.revoke(token_id)
    ok(L("Đã thu hồi token.", "Token revoked."))
    return 0


__all__ = ["create", "list_tokens", "revoke", "err"]
