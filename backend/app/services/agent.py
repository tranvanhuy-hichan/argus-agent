"""Vong lap agent: dung prompt, goi LLM (stream), chay tool, luu lich su."""
import time
from collections.abc import Callable
from datetime import datetime
from threading import Event

from ..core import config as cfgmod
from . import mcp_client, sessions, skills as skillmod, tools, usage
from .providers import ProviderError, make_provider

PROMPT_FILES = ("SOUL.md", "USER.md", "MEMORY.md")


def build_system_prompt(cfg: cfgmod.Config, skills: dict) -> str:
    ws = cfg.workspace_path()
    parts = []
    for name in PROMPT_FILES:
        p = ws / name
        if p.exists() and p.read_text().strip():
            parts.append(f"## {name}\n{p.read_text()[-4000:].strip()}")
    parts.append(f"Hien tai: {datetime.now().astimezone():%Y-%m-%d %H:%M %Z}. Workspace: {ws}.")
    block = skillmod.prompt_block(skills)
    if block:
        parts.append(block)
    return "\n\n".join(parts)


def _window(history: list[dict], limit: int) -> list[dict]:
    rest = history[-limit:]
    while rest and (rest[0]["role"] == "tool" or rest[0].get("tool_calls")):
        rest = rest[1:]
    return rest


def run_turn(sid: str, user_text: str, provider: str | None, approver: Callable[[str, str], bool],
             emit: Callable[[dict], None], cancel: Event | None = None, only_tools: list[str] | None = None) -> None:
    cfg = cfgmod.load()
    skills = skillmod.discover(cfg)
    ctx = tools.ToolContext(workspace=cfg.workspace_path(), approver=approver, confirm_exec=cfg.agent.confirm_exec,
                            env=skillmod.env_for(skills, cfg), enabled=cfg.agent.tools_enabled, skills={n: s for n, s in skills.items() if s.active})
    ctx.extra = mcp_client.manager.tool_defs()
    if only_tools is not None:  # gioi han tool cho rieng luot nay (dung cho API ben ngoai)
        ctx.enabled = {n: n in only_tools for n in [*tools.TOOLS, *ctx.extra]}
    first = provider if provider in cfg.providers else cfg.default_provider
    names = [first] + [n for n in cfg.fallback if n != first and n in cfg.providers]

    history = sessions.messages(sid)
    user_msg = {"role": "user", "content": user_text}
    sessions.add_message(sid, user_msg)
    messages = [{"role": "system", "content": build_system_prompt(cfg, skills)}] + _window(history, cfg.agent.max_history) + [user_msg]

    for _ in range(cfg.agent.max_steps):
        if cancel and cancel.is_set():
            return
        result = None
        for name in names:
            pcfg = cfg.providers[name]
            t0, started = time.time(), False
            try:
                for ev in make_provider(pcfg).stream(messages, tools.schemas(ctx)):
                    if ev["type"] == "delta":
                        started = True
                        emit(ev)
                    else:
                        result = ev
                u = result["usage"]
                usage.record_llm(name, pcfg.model, u["prompt"], u["completion"], int((time.time() - t0) * 1000), True, sid)
                result["provider"] = name
                break
            except ProviderError as e:
                usage.record_llm(name, pcfg.model, 0, 0, int((time.time() - t0) * 1000), False, sid)
                if started or name == names[-1]:
                    emit({"type": "error", "message": f"{name}: {e}"})
                    return
                emit({"type": "notice", "message": f"{name} loi, chuyen sang provider du phong"})
        msg = {"role": "assistant", "content": result["content"]}
        if result["tool_calls"]:
            msg["tool_calls"] = result["tool_calls"]
        messages.append(msg)
        sessions.add_message(sid, msg)
        if result["content"] or not result["tool_calls"]:
            emit({"type": "assistant", "content": result["content"], "provider": result["provider"], "usage": result["usage"]})
        if not result["tool_calls"]:
            return
        for c in result["tool_calls"]:
            if cancel and cancel.is_set():
                return
            emit({"type": "tool", "id": c["id"], "name": c["name"], "args": c["args"]})
            t0 = time.time()
            out, ok = tools.call(ctx, c["name"], c["args"])
            usage.record_tool(c["name"], ok, int((time.time() - t0) * 1000), sid)
            tmsg = {"role": "tool", "tool_call_id": c["id"], "content": out}
            messages.append(tmsg)
            sessions.add_message(sid, tmsg)
            emit({"type": "tool_result", "id": c["id"], "result": out[:4000], "ok": ok})
    emit({"type": "error", "message": f"vuot qua so buoc toi da ({cfg.agent.max_steps})"})
