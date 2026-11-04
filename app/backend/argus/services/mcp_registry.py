"""Tim dich vu MCP trong thu vien MCP chinh thuc (registry.modelcontextprotocol.io): chi lay cac muc co may chu tu xa."""
import httpx

URL = "https://registry.modelcontextprotocol.io/v0/servers"
KINDS = {"streamable-http": "http", "sse": "sse"}
COMMUNITY_PREFIXES = ("io.github.", "ai.smithery/", "app.", "tech.", "dev.", "xyz.")  # khong chung minh chu so huu mot thuong hieu lon


class RegistryError(Exception):
    pass


def _normalize(entry: dict) -> dict | None:
    s = entry.get("server") or {}
    remotes = [r for r in (s.get("remotes") or []) if r.get("type") in KINDS and r.get("url") and "{" not in r["url"]]
    if not remotes:
        return None
    r = remotes[0]
    name = s.get("name", "")
    headers = [h for h in (r.get("headers") or []) if h.get("name")]
    return {"id": name, "name": s.get("title") or name.split("/")[-1], "description": (s.get("description") or "")[:300], "website": s.get("websiteUrl") or "",
            "url": r["url"], "transport": KINDS[r["type"]], "publisher": name.split("/")[0],
            "community": name.startswith(COMMUNITY_PREFIXES), "needs_header": [h["name"] for h in headers if h.get("isRequired") or h.get("isSecret")]}


def search(q: str, cursor: str = "", limit: int = 30) -> dict:
    params = {"search": q.strip(), "limit": max(1, min(limit, 50))}
    if cursor:
        params["cursor"] = cursor
    try:
        r = httpx.get(URL, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    except (httpx.HTTPError, ValueError) as e:
        raise RegistryError(f"không truy cập được thư viện MCP: {type(e).__name__}") from e
    seen, items = set(), []
    for entry in data.get("servers", []):
        n = _normalize(entry)
        if n and (n["id"], n["url"]) not in seen:
            seen.add((n["id"], n["url"]))
            items.append(n)
    return {"items": items, "next": (data.get("metadata") or {}).get("nextCursor") or ""}
