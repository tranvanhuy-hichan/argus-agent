"""Tham do mot dia chi MCP tu xa: dung OAuth tu dong (co dang ky client dong), can token, hay mo san.

Khong dang nhap, khong dang ky gi: chi gui yeu cau `initialize` khong kem thong tin xac thuc va doc phan hoi.
"""
import re
from urllib.parse import urljoin, urlparse

import httpx

TIMEOUT = 12
INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "argus-probe", "version": "1"}}}
HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def _json(client: httpx.Client, url: str) -> dict | None:
    try:
        r = client.get(url)
        return r.json() if r.status_code == 200 else None
    except (httpx.HTTPError, ValueError):
        return None


def _as_metadata(client: httpx.Client, issuer: str) -> dict | None:
    u = urlparse(issuer)
    base = f"{u.scheme}://{u.netloc}"
    path = u.path.rstrip("/")
    for url in (f"{base}/.well-known/oauth-authorization-server{path}", f"{base}/.well-known/openid-configuration{path}", f"{issuer.rstrip('/')}/.well-known/openid-configuration"):
        if (m := _json(client, url)) and m.get("authorization_endpoint"):
            return m
    return None


def probe(url: str) -> dict:
    """Tra ve {kind, status, note}. kind: 'oauth' (dang nhap mot cham), 'oauth-manual' (OAuth nhung khong cho tu dang ky),
    'token' (can API token/PAT), 'open' (khong can dang nhap), 'down' (khong ket noi/khong phai MCP)."""
    try:
        with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as c:
            r = c.post(url, json=INIT, headers=HEADERS)
            if r.status_code < 300:
                return {"kind": "open", "status": r.status_code, "note": ""}
            if r.status_code not in (401, 403):
                return {"kind": "down", "status": r.status_code, "note": f"HTTP {r.status_code}"}
            prm_url = ""
            if m := re.search(r'resource_metadata="([^"]+)"', r.headers.get("www-authenticate", "")):
                prm_url = m.group(1)
            u = urlparse(url)
            candidates = [prm_url] if prm_url else []
            candidates += [f"{u.scheme}://{u.netloc}/.well-known/oauth-protected-resource{u.path.rstrip('/')}", f"{u.scheme}://{u.netloc}/.well-known/oauth-protected-resource"]
            prm = next((x for x in (_json(c, urljoin(url, p)) for p in candidates if p) if x and x.get("authorization_servers")), None)
            issuers = prm["authorization_servers"] if prm else [f"{u.scheme}://{u.netloc}"]
            meta = next((x for x in (_as_metadata(c, i) for i in issuers) if x), None)
            if not meta:
                return {"kind": "token", "status": r.status_code, "note": "không công bố OAuth"}
            if meta.get("registration_endpoint"):
                return {"kind": "oauth", "status": r.status_code, "note": ""}
            return {"kind": "oauth-manual", "status": r.status_code, "note": "OAuth nhưng không cho ứng dụng tự đăng ký"}
    except httpx.HTTPError as e:
        return {"kind": "down", "status": 0, "note": f"{type(e).__name__}: {str(e)[:80]}"}
