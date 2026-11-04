"""Provider LLM. Moi provider co stream(messages, tools) -> yield:
  {"type": "delta", "text": str}
  {"type": "final", "content": str, "tool_calls": [{"id","name","args"}], "usage": {"prompt": int, "completion": int}}
"""
import json
import os
import re
from collections.abc import Iterator

import httpx

from ..core.config import ProviderCfg

TIMEOUT = httpx.Timeout(300, connect=10)


class ProviderError(Exception):
    def __init__(self, message: str, status: int | None = None, transient: bool | None = None):
        super().__init__(message)
        self.status = status
        self.transient = transient

    @property
    def retryable(self) -> bool:
        """Loi tam thoi (qua tai, het luot, timeout) nen thu lai; loi cau hinh (401, 400, 404, khong ket noi duoc) thi khong."""
        if self.transient is not None:
            return self.transient
        return self.status in (408, 429, 500, 502, 503, 504)


def _transient(e: Exception) -> bool:
    return isinstance(e, (httpx.TimeoutException, httpx.RemoteProtocolError, httpx.ReadError)) and not isinstance(e, httpx.ConnectError)


def _key(cfg: ProviderCfg) -> str:
    return cfg.api_key or os.environ.get(cfg.api_key_env or "", "")


def _parse_args(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    try:
        v = json.loads(raw or "{}")
        return v if isinstance(v, dict) else {}
    except json.JSONDecodeError:
        return {}


SKIP_SIGNATURE = "skip_thought_signature_validator"


class OpenAICompat:
    """Ollama, OpenAI, OpenRouter, Groq... (moi API tuong thich OpenAI)."""

    def __init__(self, cfg: ProviderCfg):
        self.cfg = cfg

    def _is_gemini(self) -> bool:
        return "generativelanguage.googleapis.com" in self.cfg.base_url

    def _wire_call(self, c: dict, first: bool) -> dict:
        w = {"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": json.dumps(c["args"])}}
        if self._is_gemini():
            # Gemini 3 bat buoc gui lai thought_signature cua loi goi ham; lich su cu (hoac do model khac sinh) khong co thi dung gia tri bo qua kiem tra
            extra = c.get("extra_content") or ({"google": {"thought_signature": SKIP_SIGNATURE}} if first else None)
            if extra:
                w["extra_content"] = extra
        return w

    def _wire(self, messages: list[dict]) -> list[dict]:
        out = []
        for m in messages:
            if m.get("tool_calls"):
                m = {"role": "assistant", "content": m["content"], "tool_calls": [self._wire_call(c, i == 0) for i, c in enumerate(m["tool_calls"])]}
            if m.get("images"):
                parts = [{"type": "text", "text": m["content"]}] + [
                    {"type": "image_url", "image_url": {"url": f"data:{i['mime']};base64,{i['b64']}"}} for i in m["images"]]
                m = {"role": m["role"], "content": parts}
            out.append(m)
        return out

    def stream(self, messages: list[dict], tools: list[dict], effort: str | None = None) -> Iterator[dict]:
        headers = {"Authorization": f"Bearer {_key(self.cfg)}"} if _key(self.cfg) else {}
        body = {"model": self.cfg.model, "messages": self._wire(messages), "temperature": self.cfg.temperature,
                "stream": True, "stream_options": {"include_usage": True}}
        if tools:
            body["tools"] = [{"type": "function", "function": t} for t in tools]
        if effort in ("low", "medium", "high"):
            body["reasoning_effort"] = effort  # chi gui khi nguoi dung chon; mot so model khong nhan tham so nay
        content, calls, by_index, usage = "", [], {}, {"prompt": 0, "completion": 0}
        try:
            with httpx.stream("POST", self.cfg.base_url.rstrip("/") + "/chat/completions", json=body, headers=headers, timeout=TIMEOUT) as r:
                if r.status_code >= 400:
                    r.read()
                    raise ProviderError(f"HTTP {r.status_code}: {r.text[:300]}", r.status_code)
                for line in r.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    if chunk.get("usage"):
                        usage = {"prompt": chunk["usage"].get("prompt_tokens", 0), "completion": chunk["usage"].get("completion_tokens", 0)}
                    for ch in chunk.get("choices", []):
                        d = ch.get("delta") or {}
                        reasoning = d.get("reasoning_content") or d.get("reasoning")
                        if reasoning:
                            yield {"type": "thinking", "text": reasoning}
                        if d.get("content"):
                            content += d["content"]
                            yield {"type": "delta", "text": d["content"]}
                        for tc in d.get("tool_calls") or []:
                            fn = tc.get("function") or {}
                            idx = tc.get("index", 0)
                            # OpenAI: chunk dau cua moi loi goi co id, cac chunk sau chi co index. Gemini/mot so
                            # gateway gui index=0 cho moi loi goi, nen id moi => loi goi moi.
                            if tc.get("id") and (idx not in by_index or calls[by_index[idx]]["id"] != tc["id"]):
                                by_index[idx] = len(calls)
                                calls.append({"id": tc["id"], "name": "", "args": ""})
                            elif idx not in by_index:
                                by_index[idx] = len(calls)
                                calls.append({"id": "", "name": "", "args": ""})
                            slot = calls[by_index[idx]]
                            slot["name"] = fn.get("name") or slot["name"]
                            if tc.get("extra_content"):  # Gemini: thought_signature phai duoc gui lai o luot sau
                                slot["extra_content"] = tc["extra_content"]
                            a = fn.get("arguments")
                            if a:
                                slot["args"] = (slot["args"] + a) if isinstance(a, str) and isinstance(slot["args"], str) else a
        except httpx.HTTPError as e:
            raise ProviderError(f"{type(e).__name__}: {e}", transient=_transient(e)) from e
        tool_calls = [{"id": c["id"] or f"call_{i}", "name": c["name"], "args": _parse_args(c["args"]), **({"extra_content": c["extra_content"]} if c.get("extra_content") else {})}
                      for i, c in enumerate(calls) if c["name"]]
        yield {"type": "final", "content": content, "tool_calls": tool_calls, "usage": usage}


class Anthropic:
    def __init__(self, cfg: ProviderCfg):
        self.cfg = cfg

    def stream(self, messages: list[dict], tools: list[dict], effort: str | None = None) -> Iterator[dict]:  # noqa: ARG002 - Anthropic: chua ho tro
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        conv: list[dict] = []
        for m in messages:
            if m["role"] == "system":
                continue
            if m["role"] == "assistant" and m.get("tool_calls"):
                blocks = [{"type": "text", "text": m["content"]}] if m["content"] else []
                blocks += [{"type": "tool_use", "id": c["id"], "name": c["name"], "input": c["args"]} for c in m["tool_calls"]]
                conv.append({"role": "assistant", "content": blocks})
            elif m["role"] == "tool":
                block = {"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": m["content"]}
                if conv and conv[-1]["role"] == "user" and isinstance(conv[-1]["content"], list):
                    conv[-1]["content"].append(block)
                else:
                    conv.append({"role": "user", "content": [block]})
            elif m.get("images"):
                conv.append({"role": m["role"], "content": [
                    *[{"type": "image", "source": {"type": "base64", "media_type": i["mime"], "data": i["b64"]}} for i in m["images"]],
                    {"type": "text", "text": m["content"]}]})
            else:
                conv.append({"role": m["role"], "content": m["content"]})
        body = {"model": self.cfg.model, "max_tokens": 4096, "system": system, "messages": conv, "temperature": min(self.cfg.temperature, 1)}
        if tools:
            body["tools"] = [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]} for t in tools]
        try:
            r = httpx.post("https://api.anthropic.com/v1/messages", json=body, timeout=TIMEOUT,
                           headers={"x-api-key": _key(self.cfg), "anthropic-version": "2023-06-01"})
        except httpx.HTTPError as e:
            raise ProviderError(f"{type(e).__name__}: {e}", transient=_transient(e)) from e
        if r.status_code >= 400:
            raise ProviderError(f"HTTP {r.status_code}: {r.text[:300]}", r.status_code)
        data = r.json()
        text = "".join(b["text"] for b in data["content"] if b["type"] == "text")
        calls = [{"id": b["id"], "name": b["name"], "args": b["input"]} for b in data["content"] if b["type"] == "tool_use"]
        if text:
            yield {"type": "delta", "text": text}
        u = data.get("usage", {})
        yield {"type": "final", "content": text, "tool_calls": calls, "usage": {"prompt": u.get("input_tokens", 0), "completion": u.get("output_tokens", 0)}}


def make_provider(cfg: ProviderCfg):
    if cfg.type == "cli":
        from .cli_provider import CliProvider

        return CliProvider(cfg)
    return {"openai": OpenAICompat, "anthropic": Anthropic}[cfg.type](cfg)


NON_CHAT = re.compile(r"(tts|embed|imagen|veo|whisper|moderation|dall-e|transcribe|aqa|native-audio|-live|realtime|-image|text-to-speech|rerank|guard)", re.I)


def list_models(cfg: ProviderCfg, only_chat: bool = True) -> list[str]:
    """Hoi chinh nha cung cap xem co nhung model nao (OpenAI-compatible: /models; Anthropic: /v1/models)."""
    if cfg.type == "cli":
        from .cli_provider import list_cli_models

        return list_cli_models(cfg)
    key = _key(cfg)
    if cfg.type == "anthropic":
        url, headers = "https://api.anthropic.com/v1/models?limit=100", {"x-api-key": key, "anthropic-version": "2023-06-01"}
    else:
        url, headers = cfg.base_url.rstrip("/") + "/models", ({"Authorization": f"Bearer {key}"} if key else {})
    try:
        r = httpx.get(url, headers=headers, timeout=15)
    except httpx.HTTPError as e:
        raise ProviderError(f"{type(e).__name__}: {e}") from e
    if r.status_code >= 400:
        raise ProviderError(f"HTTP {r.status_code}: {r.text[:200]}", r.status_code)
    data = r.json()
    items = data.get("data") or data.get("models") or []
    ids = [(m.get("id") or m.get("name") or "") if isinstance(m, dict) else str(m) for m in items]
    names = {i.removeprefix("models/") for i in ids if i}
    return sorted(n for n in names if not (only_chat and NON_CHAT.search(n)))
