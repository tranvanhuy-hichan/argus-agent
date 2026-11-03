"""Client cho ClawHub public API (https://clawhub.ai/api/v1)."""
import time

import httpx

MAX_DOWNLOAD = 15 * 1024 * 1024
_cache: dict[str, tuple[float, object]] = {}


class ClawHubError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


def _norm(it: dict) -> dict:
    """Search va browse tra ve hai dang khac nhau; chuan hoa ve mot dang."""
    stats = it.get("stats") or {}
    latest = it.get("latestVersion") or {}
    trust = it.get("trust") or {}
    return {
        "slug": it["slug"],
        "owner": it.get("ownerHandle") or (it.get("owner") or {}).get("handle") or "",
        "name": it.get("displayName") or it["slug"],
        "summary": it.get("summary") or "",
        "downloads": it.get("downloads", stats.get("downloads", 0)) or 0,
        "stars": stats.get("stars", 0) or 0,
        "version": it.get("version") or latest.get("version") or (it.get("tags") or {}).get("latest"),
        "updated": it.get("updatedAt"),
        "official": bool(it.get("official")),
        "installable": trust.get("installability", "installable") == "installable",
        "topics": it.get("topics") or [],
    }


class ClawHub:
    def __init__(self, base: str):
        self.base = base.rstrip("/")

    def _get(self, path: str, params: dict | None = None, ttl: int = 0) -> httpx.Response:
        key = f"{path}?{sorted((params or {}).items())}"
        if ttl and key in _cache and _cache[key][0] > time.time():
            return _cache[key][1]
        try:
            r = httpx.get(self.base + path, params=params, timeout=30, headers={"User-Agent": "argus-agent/0.3"})
        except httpx.HTTPError as e:
            raise ClawHubError(f"không kết nối được ClawHub: {e}") from e
        if r.status_code == 429:
            raise ClawHubError("ClawHub giới hạn tốc độ, thử lại sau ít giây", 429)
        if r.status_code >= 400:
            raise ClawHubError(r.text[:300] or f"HTTP {r.status_code}", r.status_code)
        if ttl:
            _cache[key] = (time.time() + ttl, r)
        return r

    def search(self, q: str, limit: int = 24) -> list[dict]:
        r = self._get("/api/v1/search", {"q": q, "limit": limit, "nonSuspiciousOnly": "true"}, ttl=60)
        return [_norm(x) for x in r.json().get("results", [])]

    def browse(self, sort: str = "downloads", cursor: str | None = None, limit: int = 24) -> dict:
        params = {"sort": sort, "limit": limit, "nonSuspiciousOnly": "true"}
        if cursor:
            params["cursor"] = cursor
        d = self._get("/api/v1/skills", params, ttl=60).json()
        return {"items": [_norm(x) for x in d.get("items", [])], "next": d.get("nextCursor")}

    def detail(self, slug: str, owner: str) -> dict:
        d = self._get(f"/api/v1/skills/{slug}", {"ownerHandle": owner}, ttl=60).json()
        item = {**d["skill"], "ownerHandle": owner, "latestVersion": d.get("latestVersion")}
        return {**_norm(item), "moderation": d.get("moderation"), "owner_info": d.get("owner"), "metadata": d.get("metadata"),
                "changelog": (d.get("latestVersion") or {}).get("changelog"), "license": (d.get("latestVersion") or {}).get("license")}

    def preview(self, slug: str, owner: str, path: str = "SKILL.md") -> str:
        return self._get(f"/api/v1/skills/{slug}/file", {"path": path, "ownerHandle": owner, "preview": "1"}).text

    def download(self, slug: str, owner: str, version: str | None = None) -> bytes:
        params = {"slug": slug, "ownerHandle": owner}
        if version:
            params["version"] = version
        try:
            with httpx.stream("GET", self.base + "/api/v1/download", params=params, timeout=60, headers={"User-Agent": "argus-agent/0.3"}) as r:
                if r.status_code >= 400:
                    r.read()
                    raise ClawHubError(r.text[:300] or f"HTTP {r.status_code}", r.status_code)
                if "zip" not in r.headers.get("content-type", ""):
                    raise ClawHubError("skill này lưu trên GitHub (chưa hỗ trợ cài trực tiếp), hãy tải thủ công và đặt vào workspace/skills")
                buf = bytearray()
                for chunk in r.iter_bytes():
                    buf += chunk
                    if len(buf) > MAX_DOWNLOAD:
                        raise ClawHubError("file tải về quá lớn")
                return bytes(buf)
        except httpx.HTTPError as e:
            raise ClawHubError(f"không tải được: {e}") from e
