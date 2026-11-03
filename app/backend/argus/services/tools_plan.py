"""Tool lap ke hoach: plan_set / plan_update / plan_show."""
from . import plans
from .tools import ToolContext, tool


def _publish(ctx: ToolContext, items: list[dict]) -> str:
    ctx.emit({"type": "plan", "items": items})
    done, total = plans.progress(items)
    return f"Kế hoạch ({done}/{total} xong):\n{plans.render(items)}"


def _need_session(ctx: ToolContext) -> str:
    if not ctx.session_id:
        raise RuntimeError("không có hội thoại để gắn kế hoạch")
    return ctx.session_id


@tool("plan_set", "Lập kế hoạch cho việc phức tạp: danh sách các bước ngắn gọn theo thứ tự. Gọi trước khi bắt đầu làm việc nhiều bước; thay thế kế hoạch cũ.",
      {"steps": ("array", "danh sách các bước, mỗi bước một câu ngắn")})
def plan_set(ctx, steps):
    if isinstance(steps, str):
        steps = [s for s in steps.splitlines() if s.strip()]
    return _publish(ctx, plans.set_items(_need_session(ctx), list(steps)))


@tool("plan_update", "Cập nhật trạng thái một bước của kế hoạch (pending, in_progress, done, blocked) kèm ghi chú ngắn nếu cần.",
      {"step": ("integer", "số thứ tự bước (bắt đầu từ 1)"), "status": ("string", "pending, in_progress, done hoặc blocked"), "note": ("string", "ghi chú ngắn (tùy chọn)")},
      required=["step", "status"])
def plan_update(ctx, step, status, note=""):
    return _publish(ctx, plans.update(_need_session(ctx), int(step), status, note))


@tool("plan_show", "Xem lại kế hoạch hiện tại và tiến độ.", {})
def plan_show(ctx):
    items = plans.get(_need_session(ctx))
    return _publish(ctx, items) if items else "Chưa có kế hoạch. Dùng plan_set để lập."
