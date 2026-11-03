"""MCP client: ket noi cac MCP server (stdio / streamable HTTP / SSE) va dua tool cua chung vao agent.

Agent la code dong bo, con SDK MCP la async, nen moi ket noi chay trong mot event loop rieng (thread nen)
va cac loi goi tu agent di qua run_coroutine_threadsafe.
"""
import asyncio
import json
import logging
import re
import threading
from dataclasses import dataclass, field

import httpx2
from mcp import Client, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamable_http_client

from ..core.config import McpServerCfg
from .tools import ToolContext, ToolDef

log = logging.getLogger("mcp")
CONNECT_TIMEOUT = 30
CALL_TIMEOUT = 120


@dataclass
class ServerState:
    cfg: McpServerCfg
    status: str = "connecting"  # connecting | connected | error
    error: str = ""
    tools: list[dict] = field(default_factory=list)
    client: Client | None = None
    stop: asyncio.Event | None = None
    task: asyncio.Task | None = None


def _leaf_error(e: BaseException) -> str:
    while isinstance(e, BaseExceptionGroup) and e.exceptions:
        e = e.exceptions[0]
    return f"{type(e).__name__}: {e}"[:500]


def _make_client(cfg: McpServerCfg) -> Client:
    if cfg.transport == "stdio":
        if not cfg.command.strip():
            raise ValueError("thieu lenh (command) cho server stdio")
        return Client(StdioServerParameters(command=cfg.command, args=cfg.args, env=cfg.env or None, cwd=cfg.cwd or None))
    if not cfg.url.strip():
        raise ValueError("thieu URL cho server HTTP/SSE")
    if cfg.transport == "sse":
        return Client(sse_client(cfg.url, headers=cfg.headers or None))
    if cfg.headers:
        return Client(streamable_http_client(cfg.url, http_client=httpx2.AsyncClient(headers=cfg.headers, follow_redirects=True)))
    return Client(cfg.url)


def _tool_info(server: str, t) -> dict:
    ann = t.annotations
    return {
        "name": t.name,
        "full_name": re.sub(r"[^a-zA-Z0-9_-]", "_", f"{server}__{t.name}")[:64],
        "description": (t.description or t.title or "")[:1000],
        "schema": t.input_schema or {"type": "object", "properties": {}},
        "read_only": bool(ann and ann.read_only_hint),
    }


async def _list_tools(client: Client) -> list:
    tools, cursor = [], None
    for _ in range(20):
        res = await client.list_tools(cursor=cursor)
        tools += res.tools
        cursor = res.next_cursor
        if not cursor:
            break
    return tools


def _format_result(res) -> str:
    parts = []
    for b in res.content:
        kind = getattr(b, "type", "")
        if kind == "text":
            parts.append(b.text)
        elif kind in ("image", "audio"):
            parts.append(f"[{kind} {getattr(b, 'mime_type', '')}]")
        elif kind == "resource":
            r = b.resource
            parts.append(getattr(r, "text", None) or f"[resource {r.uri}]")
        else:
            parts.append(str(b))
    text = "\n".join(parts).strip()
    if not text and res.structured_content:
        text = json.dumps(res.structured_content, ensure_ascii=False)
    return text or "(khong co noi dung)"


class McpManager:
    def __init__(self) -> None:
        self.loop: asyncio.AbstractEventLoop | None = None
        self.servers: dict[str, ServerState] = {}

    # ---- vong doi
    def start(self) -> None:
        if self.loop:
            return
        ready = threading.Event()

        def run() -> None:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            ready.set()
            self.loop.run_forever()

        threading.Thread(target=run, daemon=True, name="mcp-loop").start()
        ready.wait(5)

    def stop(self) -> None:
        if not self.loop:
            return
        try:
            self._submit(self._apply({}), timeout=10)
        except Exception:  # noqa: BLE001 - tat may khong duoc phep chan
            pass
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.loop = None

    def _submit(self, coro, timeout: float | None = None):
        assert self.loop, "McpManager chua start"
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)

    # ---- dong bo cau hinh
    def apply(self, servers: dict[str, McpServerCfg]) -> None:
        """Khong chan: ket noi/ngat ket noi dien ra nen."""
        if self.loop:
            asyncio.run_coroutine_threadsafe(self._apply(servers), self.loop)

    async def _apply(self, servers: dict[str, McpServerCfg]) -> None:
        for name in list(self.servers):
            want = servers.get(name)
            if not want or not want.enabled or want != self.servers[name].cfg:
                await self._stop_server(name)
        for name, cfg in servers.items():
            if cfg.enabled and name not in self.servers:
                st = ServerState(cfg, stop=asyncio.Event())
                st.task = asyncio.get_running_loop().create_task(self._run(name, st))
                self.servers[name] = st

    async def _stop_server(self, name: str) -> None:
        st = self.servers.pop(name, None)
        if st and st.task:
            st.stop.set()
            try:
                await asyncio.wait_for(st.task, 10)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                st.task.cancel()

    async def _run(self, name: str, st: ServerState) -> None:
        try:
            async with asyncio.timeout(CONNECT_TIMEOUT) as deadline:
                async with _make_client(st.cfg) as client:
                    st.tools = [_tool_info(name, t) for t in await _list_tools(client)]
                    st.client = client
                    st.status = "connected"
                    deadline.reschedule(None)
                    await st.stop.wait()
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            st.status, st.error = "error", f"qua {CONNECT_TIMEOUT}s khong ket noi duoc"
        except BaseException as e:  # noqa: BLE001 - loi tu SDK/subprocess phai hien len UI, khong duoc nuot im
            st.status, st.error = "error", _leaf_error(e)
            log.warning("MCP %s: %s", name, st.error)
        finally:
            st.client = None

    def reconnect(self, name: str) -> None:
        cfg = self.servers[name].cfg if name in self.servers else None
        if not cfg or not self.loop:
            return

        async def go() -> None:
            await self._stop_server(name)
            await self._apply({name: cfg})

        asyncio.run_coroutine_threadsafe(go(), self.loop)

    # ---- thu ket noi voi cau hinh chua luu
    def test(self, cfg: McpServerCfg) -> dict:
        async def go() -> dict:
            try:
                async with asyncio.timeout(CONNECT_TIMEOUT):
                    async with _make_client(cfg) as client:
                        tools = [_tool_info("test", t) for t in await _list_tools(client)]
                return {"ok": True, "tools": [{"name": t["name"], "description": t["description"]} for t in tools]}
            except TimeoutError:
                return {"ok": False, "error": f"qua {CONNECT_TIMEOUT}s khong ket noi duoc"}
            except BaseException as e:  # noqa: BLE001
                return {"ok": False, "error": _leaf_error(e)}

        return self._submit(go(), timeout=CONNECT_TIMEOUT + 5)

    # ---- goi tool
    def status(self) -> dict[str, dict]:
        return {n: {"status": s.status, "error": s.error, "tools": s.tools} for n, s in self.servers.items()}

    def tool_defs(self) -> dict[str, ToolDef]:
        defs: dict[str, ToolDef] = {}
        for server, st in self.servers.items():
            if st.status != "connected":
                continue
            for t in st.tools:
                defs[t["full_name"]] = ToolDef(
                    name=t["full_name"],
                    description=f"[MCP:{server}] {t['description']}".strip(),
                    parameters=t["schema"],
                    fn=self._make_fn(server, t),
                    risk="mcp",
                )
        return defs

    def _make_fn(self, server: str, t: dict):
        def fn(ctx: ToolContext, **args):
            cfg = self.servers[server].cfg
            if cfg.confirm and not t["read_only"] and not ctx.approve("mcp", f"{t['full_name']} {json.dumps(args, ensure_ascii=False)}"):
                return "KHÔNG THỰC HIỆN: lời gọi tool bị từ chối nên CHƯA được chạy, không có kết quả nào. Hãy báo cho người dùng biết."
            return self._submit(self._call(server, t["name"], args), timeout=CALL_TIMEOUT)

        return fn

    async def _call(self, server: str, tool: str, args: dict) -> str:
        st = self.servers.get(server)
        if not st or not st.client:
            raise RuntimeError(f"MCP server '{server}' chua ket noi")
        res = await st.client.call_tool(tool, args)
        text = _format_result(res)
        if res.is_error:
            raise RuntimeError(text)
        return text


manager = McpManager()
