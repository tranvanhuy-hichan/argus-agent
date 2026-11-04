"""Hỏi đáp trên tài liệu: đọc từng định dạng, ghi vị trí, tìm kiếm kết hợp, tool, API và trạng thái lỗi."""
import zipfile

import pytest

from argus.core import config as cfgmod
from argus.services import knowledge, tools

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


@pytest.fixture(autouse=True)
def sync(tmp_env, monkeypatch):
    monkeypatch.setattr(knowledge, "_spawn", lambda fn, *a: fn(*a))


def make_pdf(path, pages):
    objs, kids = [], []
    for i, text in enumerate(pages):
        c = i * 3
        objs.append(f"<< /Type /Page /Parent {len(pages) * 3 + 1} 0 R /MediaBox [0 0 612 792] /Contents {c + 2} 0 R /Resources << /Font << /F1 {len(pages) * 3 + 2} 0 R >> >> >>")
        stream = f"BT /F1 14 Tf 72 700 Td ({text}) Tj ET"
        objs.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
        objs.append("null")
        kids.append(f"{c + 1} 0 R")
    objs.append(f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>")
    objs.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objs.append(f"<< /Type /Catalog /Pages {len(pages) * 3 + 1} 0 R >>")
    out = "%PDF-1.4\n"
    for i, o in enumerate(objs, start=1):
        out += f"{i} 0 obj\n{o}\nendobj\n"
    out += f"trailer\n<< /Size {len(objs) + 1} /Root {len(objs)} 0 R >>\nstartxref\n0\n%%EOF\n"
    path.write_bytes(out.encode("latin-1"))


def make_docx(path):
    body = ('<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Điều khoản thanh toán</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>Bên B thanh toán trong vòng 30 ngày kể từ ngày nhận hóa đơn.</w:t></w:r></w:p>'
            '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Bảo hành</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>Thời gian bảo hành là 24 tháng.</w:t></w:r></w:p>')
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", f'<?xml version="1.0"?><w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>')


def make_xlsx(path):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Doanh thu"
    ws.append(["Tháng", "Doanh thu", "Ghi chú"])
    for m in range(1, 31):
        ws.append([f"T{m}", m * 1000, "tăng mạnh" if m == 28 else ""])
    wb.save(path)


def make_pptx(path):
    A = "http://schemas.openxmlformats.org/drawingml/2006/main"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("ppt/slides/slide1.xml", f'<p:sld xmlns:p="x" xmlns:a="{A}"><a:t>Kế hoạch quý 4</a:t><a:t>Mở rộng thị trường miền Trung</a:t></p:sld>')
        z.writestr("ppt/slides/slide2.xml", f'<p:sld xmlns:p="x" xmlns:a="{A}"><a:t>Ngân sách marketing 200 triệu</a:t></p:sld>')


def test_each_format_is_read_with_its_own_location(tmp_path):
    tmp_path = tmp_path / "docs"; tmp_path.mkdir()  # tmp_path còn chứa DB của tmp_env
    make_pdf(tmp_path / "hop-dong.pdf", ["Dieu 1 Thoi han hop dong la 12 thang", "Dieu 2 Phat vi pham la 5 phan tram"])
    make_docx(tmp_path / "thoa-thuan.docx"); make_xlsx(tmp_path / "bao-cao.xlsx"); make_pptx(tmp_path / "ke-hoach.pptx")
    (tmp_path / "ghi-chu.txt").write_text("Lịch họp thứ Ba hằng tuần lúc 9 giờ sáng.\n", encoding="utf-8")
    for f in sorted(tmp_path.iterdir()):
        d = knowledge.add_file(f, f.name)
        assert knowledge.get(d["id"])["status"] == "ready", (f.name, knowledge.get(d["id"])["note"])
    pdf = knowledge.search("phat vi pham bao nhieu phan tram", 3)[0]
    assert pdf["name"] == "hop-dong.pdf" and pdf["loc"] == "trang 2"
    docx = knowledge.search("bảo hành bao lâu", 3)[0]
    assert docx["name"] == "thoa-thuan.docx" and "Bảo hành" in docx["loc"]
    xl = knowledge.search("tăng mạnh", 3)[0]
    assert xl["name"] == "bao-cao.xlsx" and xl["loc"].startswith("Doanh thu, dòng") and "Tháng" in xl["text"]  # có dòng tiêu đề đi kèm
    assert knowledge.search("ngân sách marketing", 3)[0]["loc"] == "slide 2"
    assert knowledge.search("lịch họp", 3)[0]["name"] == "ghi-chu.txt"


def test_search_is_accent_insensitive_and_semantic_path_works(tmp_path):
    cfg = cfgmod.load(); cfg.memory.embeddings = "hash"; cfgmod.save(cfg)  # vector offline
    (tmp_path / "a.txt").write_text("Doanh thu quý ba đạt 5 tỷ đồng, tăng 12% so với cùng kỳ.", encoding="utf-8")
    knowledge.add_file(tmp_path / "a.txt", "a.txt")
    hit = knowledge.search("doanh thu quy ba", 3)[0]
    assert hit["name"] == "a.txt" and set(hit["how"]) == {"từ khóa", "ngữ nghĩa"}


def test_duplicate_scanned_encrypted_and_unsupported(tmp_path):
    a = tmp_path / "x.txt"; a.write_text("nội dung đủ dài để lập chỉ mục chính xác", encoding="utf-8")
    first = knowledge.add_file(a, "x.txt")
    again = knowledge.add_file(a, "ban-sao.txt")
    assert again["id"] == first["id"] and again["duplicate"] and len(knowledge.list_docs()) == 1
    with pytest.raises(knowledge.KnowledgeError):
        knowledge.add_file(tmp_path / "x.txt", "tep.exe")
    empty = tmp_path / "trong.pdf"; make_pdf(empty, ["", ""])
    d = knowledge.add_file(empty, "trong.pdf")
    assert knowledge.get(d["id"])["status"] == "error" and "OCR" in knowledge.get(d["id"])["note"]


def test_delete_removes_chunks_vectors_and_copy(tmp_path):
    (tmp_path / "x.txt").write_text("thông tin cần xóa khỏi kho tài liệu", encoding="utf-8")
    d = knowledge.add_file(tmp_path / "x.txt", "x.txt")
    assert knowledge.search("xóa khỏi kho", 3)
    assert knowledge.delete(d["id"]) and knowledge.search("xóa khỏi kho", 3) == [] and not knowledge.has_docs()
    assert knowledge.delete(d["id"]) is False


def test_tool_hidden_when_empty_and_cites_sources(tmp_path):
    ctx = tools.ToolContext(workspace=cfgmod.load().workspace_path())
    assert not knowledge.has_docs() and "không tìm thấy" in tools.call(ctx, "kb_search", {"query": "gì đó"})[0]
    make_docx(tmp_path / "tt.docx"); knowledge.add_file(tmp_path / "tt.docx", "tt.docx")
    out = tools.call(ctx, "kb_search", {"query": "thanh toán trong bao nhiêu ngày"})[0]
    assert "[[src:" in out and "|tt.docx|" in out and "30 ngày" in out
    from argus.services import agent
    assert "kb_search" in agent.knowledge_note() and "tt" not in agent.knowledge_note()[:0]


def test_folder_import_skips_hidden_and_unsupported(tmp_path):
    d = tmp_path / "kho"; (d / "con").mkdir(parents=True); (d / ".git").mkdir()
    (d / "con" / "a.md").write_text("# Quy trình\nBước một là kiểm tra hồ sơ.", encoding="utf-8")
    (d / ".git" / "b.txt").write_text("ẩn không lấy", encoding="utf-8"); (d / "anh.png").write_bytes(b"png")
    r = knowledge.add_folder(d)
    assert r["added"] == 1 and r["skipped"] == 1 and knowledge.list_docs()[0]["name"].endswith("a.md")


def test_api_upload_search_download_delete(tmp_path):
    from fastapi.testclient import TestClient

    from argus.main import app
    c = TestClient(app)
    r = c.post("/api/knowledge/upload", params={"name": "chinh-sach.txt"}, content="Nhân viên được nghỉ phép 12 ngày mỗi năm.".encode())
    assert r.status_code == 200, r.text
    did = r.json()["id"]
    assert c.get("/api/knowledge").json()["stats"]["docs"] == 1
    hit = c.post("/api/knowledge/search", json={"query": "nghỉ phép mấy ngày"}).json()[0]
    assert hit["name"] == "chinh-sach.txt" and "12 ngày" in hit["text"]
    assert "12 ngày" in c.get(f"/api/knowledge/{did}/file").text
    assert c.post("/api/knowledge/upload", params={"name": "a.exe"}, content=b"x").status_code == 400
    assert c.post("/api/knowledge/search", json={"query": " "}).status_code == 400
    assert c.delete(f"/api/knowledge/{did}").status_code == 200 and c.delete(f"/api/knowledge/{did}").status_code == 404


def test_ask_from_documents_option_restricts_tools_and_requires_sources(tmp_path, monkeypatch):
    from argus.services import agent as agent_mod
    from argus.services import sessions
    seen = {}

    class Fake:
        def stream(self, messages, tool_defs, effort=None):
            seen["tools"] = {t["name"] for t in tool_defs}; seen["system"] = messages[0]["content"]
            yield {"type": "delta", "text": "ok"}
            yield {"type": "final", "content": "ok", "tool_calls": [], "usage": {"prompt": 1, "completion": 1}}

    monkeypatch.setattr(agent_mod, "make_provider", lambda cfg: Fake())
    events = []
    agent_mod.run_turn(sessions.create("x"), "bảo hành bao lâu?", None, lambda k, d: True, events.append, use_docs=True)
    assert any(e["type"] == "notice" for e in events) and "kb_search" not in seen["tools"]  # kho trống: trả lời bình thường
    (tmp_path / "x.txt").write_text("Bảo hành 24 tháng kể từ ngày bàn giao thiết bị.", encoding="utf-8")
    knowledge.add_file(tmp_path / "x.txt", "x.txt")
    agent_mod.run_turn(sessions.create("y"), "bảo hành bao lâu?", None, lambda k, d: True, lambda e: None, use_docs=True)
    assert seen["tools"] == {"kb_search"} and "HỎI TỪ TÀI LIỆU" in seen["system"] and "[[src:" in seen["system"]
    assert "24 tháng" in seen["system"] and "đã tìm sẵn" in seen["system"]  # đoạn liên quan được đưa sẵn vào, model có thể trả lời ngay
    agent_mod.run_turn(sessions.create("z"), "xin chào", None, lambda k, d: True, lambda e: None)  # không bật tùy chọn: đủ công cụ, kb_search chỉ là một trong số đó
    assert "kb_search" in seen["tools"] and "read" in seen["tools"]


def test_chat_api_accepts_docs_flag(monkeypatch):
    from fastapi.testclient import TestClient

    from argus.main import app
    from argus.services import chat_runner
    got = {}
    monkeypatch.setattr(chat_runner, "stream_chat", lambda *a, **k: iter([got.update(k) or {"type": "done"}]))
    r = TestClient(app).post("/api/chat", json={"text": "hi", "docs": True})
    assert r.status_code == 200 and got["docs"] is True


def test_ensure_vectors_after_enabling_embeddings_enables_semantic_hits(tmp_path):
    (tmp_path / "a.txt").write_text("Doanh thu quý ba đạt 5 tỷ đồng, tăng 12% so với cùng kỳ năm trước.", encoding="utf-8")
    knowledge.add_file(tmp_path / "a.txt", "a.txt")  # embedding đang tắt: chưa có vector nào
    assert "ngữ nghĩa" not in knowledge.search("doanh thu quý ba", 3)[0]["how"]
    cfg = cfgmod.load(); cfg.memory.embeddings = "hash"; cfgmod.save(cfg)
    assert knowledge.ensure_vectors() == 1 and knowledge.ensure_vectors() == 0  # lần hai không còn gì để nhúng
    assert "ngữ nghĩa" in knowledge.search("doanh thu quý ba", 3)[0]["how"]


# ---------- API ngoài (/v1/documents), MCP và phân tích tài liệu
@pytest.fixture
def ext(tmp_env):
    from fastapi.testclient import TestClient

    from argus.main import app
    from argus.services import tokens
    c = TestClient(app)
    _, read = tokens.create("chi-doc", False)
    _, write = tokens.create("ghi", False, True)
    return c, {"Authorization": f"Bearer {read}"}, {"Authorization": f"Bearer {write}"}


def test_v1_documents_scopes_upload_search_delete(ext):
    c, r_hdr, w_hdr = ext
    assert c.get("/v1/documents").status_code == 401
    assert c.post("/v1/documents", params={"name": "a.txt"}, content=b"x", headers=r_hdr).status_code == 403  # token chỉ đọc không được thêm
    up = c.post("/v1/documents", params={"name": "chinh-sach.txt"}, content="Nhân viên được nghỉ phép 12 ngày mỗi năm.".encode(), headers=w_hdr)
    assert up.status_code == 200 and up.json()["status"] in ("indexing", "ready")
    assert c.get("/v1/documents", headers=r_hdr).json()[0]["name"] == "chinh-sach.txt"
    hit = c.post("/v1/documents/search", json={"query": "nghỉ phép mấy ngày"}, headers=r_hdr).json()[0]
    assert hit["name"] == "chinh-sach.txt" and "12 ngày" in hit["text"] and "how" not in hit
    assert c.post("/v1/documents/search", json={"query": ""}, headers=r_hdr).status_code == 422
    did = hit["doc_id"]
    assert c.delete(f"/v1/documents/{did}", headers=r_hdr).status_code == 403
    assert c.delete(f"/v1/documents/{did}", headers=w_hdr).status_code == 200 and c.get("/v1/documents", headers=r_hdr).json() == []


def test_v1_ask_returns_answer_with_plain_sources(ext, tmp_path, monkeypatch):
    c, r_hdr, w_hdr = ext
    assert c.post("/v1/documents/ask", json={"question": "hỏi"}, headers=r_hdr).status_code == 400  # kho trống
    (tmp_path / "bh.txt").write_text("Thời gian bảo hành là 24 tháng.", encoding="utf-8")
    d = knowledge.add_file(tmp_path / "bh.txt", "bh.txt")
    from argus.services import agent as agent_mod
    tag = f"[[src:{d['id']}|bh.txt|dòng 1-1]]"

    class Fake:
        def stream(self, messages, tool_defs, effort=None):
            yield {"type": "delta", "text": "x"}
            yield {"type": "final", "content": f"Bảo hành 24 tháng {tag}.", "tool_calls": [], "usage": {"prompt": 1, "completion": 1}}

    monkeypatch.setattr(agent_mod, "make_provider", lambda cfg: Fake())
    r = c.post("/v1/documents/ask", json={"question": "bảo hành bao lâu?"}, headers=r_hdr).json()
    assert r["answer"] == "Bảo hành 24 tháng [bh.txt, dòng 1-1]." and r["sources"] == [{"doc_id": d["id"], "name": "bh.txt", "loc": "dòng 1-1"}] and r["error"] is None


def test_mcp_tools_call_the_rest_api(monkeypatch, tmp_path):
    import json

    import argus.mcp_server as m
    calls = []
    monkeypatch.setattr(m, "_call", lambda method, path, body=None, timeout=0, **kw: calls.append((method, path, body, kw)) or {"ok": True, "answer": "a", "sources": [{"name": "f.pdf", "loc": "trang 2"}], "session": "s"})
    f = tmp_path / "bao-cao.txt"; f.write_text("nội dung", encoding="utf-8")
    assert json.loads(m.kb_upload(str(f)))["ok"]
    m.kb_list(); m.kb_search("giá", 3); m.kb_delete("abc")
    out = m.kb_ask("câu hỏi?")
    assert "f.pdf, trang 2" in out and "a" in out
    assert [c[:2] for c in calls] == [("POST", "/v1/documents"), ("GET", "/v1/documents"), ("POST", "/v1/documents/search"), ("DELETE", "/v1/documents/abc"), ("POST", "/v1/documents/ask")]
    assert calls[0][3]["params"] == {"name": "bao-cao.txt"} and calls[0][3]["raw"] == "nội dung".encode()
    with pytest.raises(RuntimeError):
        m.kb_upload(str(tmp_path / "khong-co.pdf"))


def test_analysis_job_uses_only_documents_and_gets_overview(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from argus.main import app
    from argus.services import agent as agent_mod
    from argus.services import jobs
    c = TestClient(app)
    assert c.post("/api/knowledge/analyze", json={}).status_code == 400
    (tmp_path / "dc.txt").write_text("Dự án cải tạo nhà văn hóa. Thời hạn 90 ngày. Kinh phí 500 triệu đồng.", encoding="utf-8")
    knowledge.add_file(tmp_path / "dc.txt", "dc.txt")
    seen = {}

    class Fake:
        def stream(self, messages, tool_defs, effort=None):
            seen["tools"] = {t["name"] for t in tool_defs}; seen["system"] = messages[0]["content"]
            yield {"type": "delta", "text": "báo cáo"}
            yield {"type": "final", "content": "## Tóm tắt\nbáo cáo", "tool_calls": [], "usage": {"prompt": 1, "completion": 1}}

    monkeypatch.setattr(agent_mod, "make_provider", lambda cfg: Fake())
    jid = jobs.create("Phân tích rủi ro", kind="analysis", title="Phân tích tài liệu", permission="readonly")
    done = jobs.execute(jid)
    assert done["status"] == "done" and "Tóm tắt" in done["result"]
    assert seen["tools"] == {"kb_search"} and "PHÂN TÍCH TÀI LIỆU" in seen["system"] and "500 triệu" in seen["system"] and "[[src:" in seen["system"]


def test_passage_returns_only_that_chunk_text(tmp_env, tmp_path):
    from fastapi.testclient import TestClient
    from argus.main import app
    from argus.services import knowledge
    f = tmp_path / "note.txt"
    f.write_text("Alpha paragraph about budgets.\n\nBeta paragraph about schedules.")
    doc = knowledge.add_file(f, "note.txt")
    from argus.core.db import db
    with db() as c:
        loc = c.execute("SELECT loc FROM kb_chunks WHERE doc_id=? ORDER BY ord LIMIT 1", (doc["id"],)).fetchone()["loc"]
    r = TestClient(app).get(f"/api/knowledge/{doc['id']}/passage", params={"loc": loc})
    assert r.status_code == 200 and "budgets" in r.json()["text"] and r.json()["name"].endswith("note.txt") and r.json()["has_file"]
    assert TestClient(app).get("/api/knowledge/nope/passage", params={"loc": "x"}).status_code == 404


def test_telegram_reply_sources_become_footer():
    from argus.services.telegram_channel import clean_reply
    out = clean_reply("Cần có ngân sách. [[src:ab12|bao-cao.docx|đoạn 1-32]] Và tiến độ. [[src:ab12|bao-cao.docx|đoạn 1-32]]")
    assert "[[" not in out and out.endswith("Nguồn: bao-cao.docx (đoạn 1-32)") and out.startswith("Cần có ngân sách. Và tiến độ.")
