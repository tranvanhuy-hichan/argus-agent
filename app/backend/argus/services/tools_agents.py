"""Tool giao viec: delegate (agent con), task_start/task_status/task_cancel (viec chay nen)."""
from ..core import config as cfgmod
from . import jobs
from .tools import ToolContext, tool


def _result_text(job: dict, label: str) -> str:
    head = f"{label} (job {job['id']}, {job['steps']} bước, {job['status']})"
    if job["status"] == "done":
        return f"{head}:\n{job['result'] or '(không có kết quả)'}"
    return f"{head} KHÔNG thành công: {job['error'] or 'bị dừng'}" + (f"\nKết quả dở dang: {job['result']}" if job["result"] else "")


@tool("delegate", "Giao một việc cho agent con chuyên trách rồi nhận kết quả (chạy xong mới trả về). Dùng khi việc cần chuyên môn riêng hoặc muốn làm song song: gọi nhiều delegate trong cùng một lượt để chạy đồng thời. Vai trò có sẵn: researcher, coder, reviewer, general.",
      {"role": ("string", "vai trò: researcher, coder, reviewer hoặc general"), "task": ("string", "mô tả đầy đủ việc cần làm và kết quả mong muốn (agent con không thấy hội thoại này)")})
def delegate(ctx: ToolContext, role, task):
    if not task.strip():
        raise ValueError("thiếu mô tả việc cần giao")
    return _result_text(jobs.run_subagent(ctx, role.strip().lower() or "general", task.strip()), f"Agent con '{role}'")


@tool("task_start", "Bắt đầu một VIỆC CHẠY NỀN (có thể kéo dài nhiều phút, nhiều bước) rồi trả lời người dùng ngay. Khi xong sẽ có thông báo. Dùng cho việc lớn không cần chờ kết quả ngay.",
      {"goal": ("string", "mục tiêu đầy đủ, tự chứa mọi thông tin cần thiết"), "title": ("string", "tên ngắn của việc"), "role": ("string", "vai trò (tùy chọn): researcher, coder, reviewer, general")},
      required=["goal"])
def task_start(ctx: ToolContext, goal, title="", role="general"):
    cfg = cfgmod.load()
    if ctx.depth >= cfg.agents.max_depth:
        raise ValueError("agent con không được tạo việc nền")
    jid = jobs.start_background(goal.strip(), kind="task", title=title or goal[:60], role=(role or "general").lower(), parent_session=ctx.session_id, permission=ctx.permission, provider=ctx.provider)
    return f"Đã bắt đầu việc nền {jid} ({title or goal[:60]}). Chạy ngầm; dùng task_status {jid} để xem tiến độ. Người dùng sẽ nhận thông báo khi xong."


@tool("task_status", "Xem tiến độ một việc chạy nền (theo id) hoặc liệt kê các việc gần đây.", {"id": ("string", "id việc nền; bỏ trống để liệt kê")}, required=[])
def task_status(ctx: ToolContext, id=""):
    if id:
        job = jobs.get(id)
        if not job:
            return f"không có việc '{id}'"
        return f"{job['title']} [{job['status']}] {job['steps']}/{job['max_steps'] or '?'} bước" + (f"\nĐang: {job['progress']}" if job["progress"] else "") + (f"\nKết quả:\n{job['result']}" if job["result"] else "") + (f"\nLỗi: {job['error']}" if job["error"] else "")
    rows = jobs.list_jobs(kind="task", limit=10)
    return "\n".join(f"{j['id']}  [{j['status']}]  {j['title']}  ({j['steps']} bước)" for j in rows) or "chưa có việc nền nào"


@tool("task_cancel", "Hủy một việc chạy nền đang chạy.", {"id": ("string", "id việc nền")})
def task_cancel(ctx: ToolContext, id):
    return "đã yêu cầu hủy" if jobs.request_cancel(id) else f"không hủy được '{id}' (không tồn tại hoặc đã kết thúc)"
