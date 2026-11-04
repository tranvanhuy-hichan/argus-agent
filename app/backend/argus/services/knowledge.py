"""Hỏi đáp trên tài liệu của người dùng: nhận PDF, Word, Excel, PowerPoint và văn bản, cắt thành đoạn có ghi vị trí (trang, sheet, slide),
lập chỉ mục từ khóa (FTS5) và vector, rồi tìm kết hợp. Nguồn gốc của mọi câu trả lời là `(tên file, vị trí)` để người dùng kiểm chứng."""
import csv
import hashlib
import io
import json
import logging
import re
import shutil
import threading
import time
import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from ..core import config as cfgmod
from ..core.db import db
from ..core.text import fold
from . import embeddings, vectorstore
from .memory_index import chunk_text

log = logging.getLogger("argus.knowledge")
MAX_UPLOAD = 60 * 1024 * 1024
MAX_CHUNKS = 6000
MAX_PAGES = 3000
MAX_FOLDER_FILES = 500
MAX_UNZIPPED = 300 * 1024 * 1024
CHUNK = 900
RRF_K = 60
SUPPORTED = {".pdf", ".docx", ".xlsx", ".xlsm", ".pptx", ".txt", ".md", ".csv", ".tsv", ".json", ".log", ".html", ".htm", ".xml", ".rst"}


ANALYSIS_PROMPT = ("PHÂN TÍCH TÀI LIỆU. Đọc kỹ các đoạn tài liệu đã cho (phần mở đầu của từng tài liệu cùng các đoạn khớp với trọng tâm), gọi kb_search thêm nhiều lần với từ khóa khác nhau "
                   "để tìm các mục còn thiếu (yêu cầu, thời hạn, chi phí, ràng buộc, rủi ro), rồi viết báo cáo bằng Markdown, ngôn ngữ của người dùng, theo đúng cấu trúc:\n"
                   "## Tóm tắt\n(3-5 câu)\n## Yêu cầu và ràng buộc chính\n(gạch đầu dòng)\n## Rủi ro và điểm chưa rõ\n(gạch đầu dòng, nêu cả những gì tài liệu không nói)\n"
                   "## Phương án đề xuất\n(2-3 phương án; mỗi phương án nêu cách làm, ưu điểm, nhược điểm)\n## Khuyến nghị\n(chọn một phương án và giải thích lý do)\n## Các bước thực hiện\n(danh sách đánh số, có thứ tự và thời hạn nếu tài liệu nêu)\n"
                   "Sau mỗi ý dựa vào tài liệu, chèn nguyên văn thẻ nguồn [[src:...]] lấy từ các đoạn đã cho hoặc từ kb_search (đặt cuối câu). Ý nào là suy luận của bạn, không phải của tài liệu, ghi rõ là đề xuất. Tuyệt đối không bịa số liệu.")


class KnowledgeError(ValueError):
    pass


def ensure_schema() -> None:
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS kb_docs(
            id TEXT PRIMARY KEY, name TEXT NOT NULL, path TEXT, source TEXT, ext TEXT, size INTEGER, sha TEXT UNIQUE,
            pages INTEGER DEFAULT 0, chunks INTEGER DEFAULT 0, status TEXT, note TEXT, added REAL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS kb_chunks(
            id INTEGER PRIMARY KEY AUTOINCREMENT, doc_id TEXT NOT NULL, ord INTEGER, loc TEXT, text TEXT NOT NULL)""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_kbc_doc ON kb_chunks(doc_id, ord)")
        c.execute("""CREATE TABLE IF NOT EXISTS kb_vecs(
            chunk_id INTEGER NOT NULL, model TEXT NOT NULL, dim INTEGER, vec BLOB, PRIMARY KEY(chunk_id, model))""")
        try:
            c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS kb_fts USING fts5(folded, chunk_id UNINDEXED)")
        except Exception:  # noqa: BLE001 - không có FTS5 thì lùi về LIKE
            pass


def _fts(c) -> bool:
    return c.execute("SELECT 1 FROM sqlite_master WHERE name='kb_fts'").fetchone() is not None


# ---------- đọc từng loại file: trả về [(vị trí, văn bản)]
def _guard_zip(z: zipfile.ZipFile) -> None:
    if sum(i.file_size for i in z.infolist()) > MAX_UNZIPPED:
        raise KnowledgeError("file nén quá lớn để mở an toàn")


def _read_pdf(path: Path) -> tuple[list[tuple[str, str]], int, str]:
    from pypdf import PdfReader
    r = PdfReader(str(path))
    if r.is_encrypted and not r.decrypt(""):
        raise KnowledgeError("PDF có mật khẩu, hãy gỡ mật khẩu rồi thêm lại")
    out, blank = [], 0
    n = min(len(r.pages), MAX_PAGES)
    for i in range(n):
        try:
            t = (r.pages[i].extract_text() or "").strip()
        except Exception:  # noqa: BLE001 - một trang hỏng không làm hỏng cả file
            t = ""
        if t:
            out.append((f"trang {i + 1}", t))
        else:
            blank += 1
    note = f"{blank}/{n} trang không có chữ (có thể là bản quét ảnh, cần OCR)" if blank and blank >= max(1, n // 2) else ""
    return out, n, note


def _xml_text(root: ET.Element, ns: str, tag: str) -> str:
    return "".join(t.text or "" for t in root.iter(f"{{{ns}}}{tag}"))


def _read_docx(path: Path) -> tuple[list[tuple[str, str]], int, str]:
    W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    with zipfile.ZipFile(path) as z:
        _guard_zip(z)
        root = ET.fromstring(z.read("word/document.xml"))
    segs, buf, start, heading, n = [], [], 1, "", 0
    def flush() -> None:
        nonlocal buf
        if buf:
            segs.append((f"mục “{heading}”" if heading else f"đoạn {start}-{n}", "\n".join(buf)))
            buf = []
    for p in root.iter(f"{{{W}}}p"):
        text = _xml_text(p, W, "t").strip()
        style = p.find(f"{{{W}}}pPr/{{{W}}}pStyle")
        is_h = style is not None and (style.get(f"{{{W}}}val") or "").lower().startswith(("heading", "title"))
        if not text:
            continue
        n += 1
        if is_h:
            flush()
            heading, start = text[:80], n
        if not buf:
            start = n
        buf.append(text)
        if sum(len(x) for x in buf) > CHUNK * 2:
            flush()
    flush()
    return segs, 0, ""


def _read_xlsx(path: Path) -> tuple[list[tuple[str, str]], int, str]:
    import openpyxl
    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    segs = []
    for ws in wb.worksheets:
        header, buf, first = "", [], 1
        for i, row in enumerate(ws.iter_rows(values_only=True), start=1):
            cells = ["" if v is None else str(v).strip() for v in row]
            if not any(cells):
                continue
            line = " | ".join(cells).rstrip(" |")
            if not header:
                header = line
            if not buf:
                first = i
            buf.append(line)
            if len(buf) >= 25:
                segs.append((f"{ws.title}, dòng {first}-{i}", "\n".join(([header] if first > 1 and header not in buf else []) + buf)))
                buf = []
        if buf:
            segs.append((f"{ws.title}, dòng {first}-{first + len(buf) - 1}", "\n".join(([header] if first > 1 and header not in buf else []) + buf)))
    wb.close()
    return segs, len(wb.worksheets), ""


def _read_pptx(path: Path) -> tuple[list[tuple[str, str]], int, str]:
    A = "http://schemas.openxmlformats.org/drawingml/2006/main"
    segs = []
    with zipfile.ZipFile(path) as z:
        _guard_zip(z)
        names = sorted((n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)), key=lambda s: int(re.findall(r"\d+", s)[-1]))
        for i, n in enumerate(names, start=1):
            root = ET.fromstring(z.read(n))
            text = "\n".join(t.strip() for t in (x.text or "" for x in root.iter(f"{{{A}}}t")) if t.strip())
            if text:
                segs.append((f"slide {i}", text))
    return segs, len(segs), ""


def _read_text(path: Path, ext: str) -> tuple[list[tuple[str, str]], int, str]:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-16", "cp1258", "cp1252"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeError:
            continue
    else:
        text = raw.decode("utf-8", "replace")
    if ext in (".html", ".htm", ".xml"):
        text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", text)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
    elif ext in (".csv", ".tsv"):
        rows = csv.reader(io.StringIO(text), delimiter="\t" if ext == ".tsv" else ",")
        text = "\n".join(" | ".join(r) for r in rows)
    elif ext == ".json":
        try:
            text = json.dumps(json.loads(text), ensure_ascii=False, indent=1)
        except ValueError:
            pass
    lines = [ln for ln in text.splitlines()]
    segs, step = [], 40
    for i in range(0, len(lines), step):
        part = "\n".join(lines[i:i + step]).strip()
        if part:
            segs.append((f"dòng {i + 1}-{min(i + step, len(lines))}", part))
    return segs, 0, ""


def extract(path: Path, ext: str) -> tuple[list[tuple[str, str]], int, str]:
    ext = ext.lower()
    if ext == ".pdf":
        return _read_pdf(path)
    if ext == ".docx":
        return _read_docx(path)
    if ext in (".xlsx", ".xlsm"):
        return _read_xlsx(path)
    if ext == ".pptx":
        return _read_pptx(path)
    if ext in SUPPORTED:
        return _read_text(path, ext)
    raise KnowledgeError(f"chưa hỗ trợ định dạng {ext or 'này'} (hỗ trợ: PDF, Word .docx, Excel .xlsx, PowerPoint .pptx, văn bản)")


# ---------- thêm / xóa tài liệu
def _store_dir(cfg) -> Path:
    return cfg.workspace_path() / "knowledge"


def _spawn(fn, *args) -> None:
    threading.Thread(target=fn, args=args, daemon=True, name="kb-index").start()


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def add_file(src: Path, name: str, source: str = "upload", *, keep_copy: bool = True) -> dict:
    """Thêm một file vào kho. Trùng nội dung (sha256) thì trả lại tài liệu đã có. Việc đọc và lập chỉ mục chạy nền."""
    ensure_schema()
    ext = Path(name).suffix.lower()
    if ext not in SUPPORTED:
        raise KnowledgeError(f"chưa hỗ trợ định dạng {ext or 'này'} (hỗ trợ: PDF, Word .docx, Excel .xlsx, PowerPoint .pptx, văn bản)")
    size = src.stat().st_size
    if size > MAX_UPLOAD:
        raise KnowledgeError("file quá lớn (tối đa 60MB)")
    sha = _sha(src)
    with db() as c:
        dup = c.execute("SELECT * FROM kb_docs WHERE sha=?", (sha,)).fetchone()
    if dup:
        return {**dict(dup), "duplicate": True}
    cfg = cfgmod.load()
    did = uuid.uuid4().hex[:8]
    path = str(src)
    if keep_copy:
        d = _store_dir(cfg) / did
        d.mkdir(parents=True, exist_ok=True)
        dest = d / re.sub(r"[^\w.\- ()]", "_", name)[:120]
        shutil.copyfile(src, dest)
        path = str(dest)
    with db() as c:
        c.execute("INSERT INTO kb_docs(id,name,path,source,ext,size,sha,status,added) VALUES(?,?,?,?,?,?,?,?,?)", (did, name[:200], path, source, ext, size, sha, "indexing", time.time()))
    _spawn(_index, did)
    return get(did) or {}


def _index(did: str) -> None:
    ensure_schema()
    with db() as c:
        d = c.execute("SELECT * FROM kb_docs WHERE id=?", (did,)).fetchone()
    if not d:
        return
    try:
        segs, pages, note = extract(Path(d["path"]), d["ext"])
        rows: list[tuple[str, str]] = []
        for loc, text in segs:
            for ch in chunk_text(text, CHUNK):
                if len(ch) >= 12:
                    rows.append((loc, ch))
        if len(rows) > MAX_CHUNKS:
            rows, note = rows[:MAX_CHUNKS], (note + " " if note else "") + f"chỉ lập chỉ mục {MAX_CHUNKS} đoạn đầu"
        if not rows:
            raise KnowledgeError(note or "không đọc được chữ nào trong file")
        with db() as c:
            c.execute("DELETE FROM kb_chunks WHERE doc_id=?", (did,))
            ids = []
            for i, (loc, text) in enumerate(rows):
                cur = c.execute("INSERT INTO kb_chunks(doc_id,ord,loc,text) VALUES(?,?,?,?)", (did, i, loc, text))
                ids.append(cur.lastrowid)
            if _fts(c):
                c.executemany("INSERT INTO kb_fts(folded, chunk_id) VALUES(?,?)", [(fold(t), cid) for cid, (_, t) in zip(ids, rows)])
        vec_note = _embed_chunks(ids, [t for _, t in rows])
        note = " ".join(x for x in (note, vec_note) if x)
        with db() as c:
            c.execute("UPDATE kb_docs SET status='ready', pages=?, chunks=?, note=? WHERE id=?", (pages, len(rows), note, did))
    except Exception as e:  # noqa: BLE001 - tài liệu lỗi chỉ đánh dấu lỗi, không làm hỏng server
        log.info("index %s lỗi: %s", did, e)
        with db() as c:
            c.execute("UPDATE kb_docs SET status='error', note=? WHERE id=?", (str(e)[:300], did))


def _embed_chunks(ids: list[int], texts: list[str]) -> str:
    """Nhúng vector theo lô. Lỗi (Ollama tắt...) thì vẫn tìm được bằng từ khóa; trả về ghi chú nếu có."""
    cfg = cfgmod.load()
    if cfg.memory.embeddings == "off":
        return ""
    try:
        for i in range(0, len(ids), 32):
            vecs, model = embeddings.embed(cfg, texts[i:i + 32])
            with db() as c:
                c.executemany("INSERT OR REPLACE INTO kb_vecs(chunk_id,model,dim,vec) VALUES(?,?,?,?)",
                              [(cid, model, len(v), vectorstore._pack(v)) for cid, v in zip(ids[i:i + 32], vecs)])
    except Exception as e:  # noqa: BLE001
        return f"chưa nhúng được vector ({str(e)[:80]}), vẫn tìm được theo từ khóa"
    return ""


_ensuring = threading.Lock()


def ensure_vectors() -> int:
    """Nhúng vector cho các đoạn chưa có vector của model embedding hiện tại (sau khi bật embedding hoặc đổi model). Trả về số đoạn đã nhúng."""
    cfg = cfgmod.load()
    if cfg.memory.embeddings == "off" or not _ensuring.acquire(blocking=False):
        return 0
    try:
        ensure_schema()
        e = embeddings.get_embedder(cfg)
        if e is None:
            return 0
        with db() as c:
            rows = c.execute("SELECT c.id, c.text FROM kb_chunks c LEFT JOIN kb_vecs v ON v.chunk_id=c.id AND v.model=? WHERE v.chunk_id IS NULL", (e.model_id,)).fetchall()
        done = 0
        for i in range(0, len(rows), 32):
            part = rows[i:i + 32]
            vecs, model = e.embed([r["text"] for r in part])
            with db() as c:
                c.executemany("INSERT OR REPLACE INTO kb_vecs(chunk_id,model,dim,vec) VALUES(?,?,?,?)", [(r["id"], model, len(v), vectorstore._pack(v)) for r, v in zip(part, vecs)])
            done += len(part)
        return done
    except Exception as ex:  # noqa: BLE001
        log.info("ensure_vectors: %s", ex)
        return 0
    finally:
        _ensuring.release()


def add_bytes(name: str, data: bytes, source: str = "upload") -> dict:
    """Thêm tài liệu từ nội dung file thô (tải lên qua giao diện hoặc API)."""
    import tempfile
    if len(data) > MAX_UPLOAD:
        raise KnowledgeError("file quá lớn (tối đa 60MB)")
    clean = re.sub(r"[\\/]+", "/", name).split("/")[-1].strip() or "tai-lieu"
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / clean
        src.write_bytes(data)
        return add_file(src, name.replace("\\", "/")[-200:], source)


SRC_TAG = re.compile(r"\[\[src:([^|\]]+)\|([^|\]]+)\|([^\]]+)\]\]")


def plain_sources(text: str) -> tuple[str, list[dict]]:
    """Với ứng dụng bên ngoài: đổi thẻ nguồn [[src:...]] thành chữ thường `[tên file, vị trí]` và trả danh sách nguồn không trùng."""
    seen: dict[tuple, dict] = {}
    for m in SRC_TAG.finditer(text):
        seen.setdefault((m.group(1), m.group(3)), {"doc_id": m.group(1).strip(), "name": m.group(2).strip(), "loc": m.group(3).strip()})
    return SRC_TAG.sub(lambda m: f"[{m.group(2).strip()}, {m.group(3).strip()}]", text), list(seen.values())


def add_folder(folder: Path) -> dict:
    """Thêm mọi file được hỗ trợ trong một thư mục (đệ quy, bỏ thư mục ẩn). Giữ bản sao để file di chuyển cũng không mất."""
    if not folder.is_dir():
        raise KnowledgeError("không phải thư mục")
    added, dup, skipped = 0, 0, 0
    files = [p for p in sorted(folder.rglob("*")) if p.is_file() and not any(part.startswith(".") for part in p.relative_to(folder).parts)]
    for p in files:
        if p.suffix.lower() not in SUPPORTED:
            skipped += 1
            continue
        if added + dup >= MAX_FOLDER_FILES:
            skipped += 1
            continue
        try:
            r = add_file(p, str(p.relative_to(folder)), "folder")
            dup += 1 if r.get("duplicate") else 0
            added += 0 if r.get("duplicate") else 1
        except KnowledgeError:
            skipped += 1
    return {"added": added, "duplicates": dup, "skipped": skipped}


def get(did: str) -> dict | None:
    ensure_schema()
    with db() as c:
        r = c.execute("SELECT * FROM kb_docs WHERE id=?", (did,)).fetchone()
    return dict(r) if r else None


def list_docs() -> list[dict]:
    ensure_schema()
    with db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM kb_docs ORDER BY added DESC")]


def has_docs() -> bool:
    try:
        ensure_schema()
        with db() as c:
            return c.execute("SELECT 1 FROM kb_docs WHERE status='ready' LIMIT 1").fetchone() is not None
    except Exception:  # noqa: BLE001
        return False


def delete(did: str) -> bool:
    ensure_schema()
    d = get(did)
    if not d:
        return False
    with db() as c:
        ids = [r["id"] for r in c.execute("SELECT id FROM kb_chunks WHERE doc_id=?", (did,))]
        for i in range(0, len(ids), 500):
            part = ids[i:i + 500]
            q = ",".join("?" * len(part))
            c.execute(f"DELETE FROM kb_vecs WHERE chunk_id IN ({q})", part)
            if _fts(c):
                c.execute(f"DELETE FROM kb_fts WHERE chunk_id IN ({q})", part)
        c.execute("DELETE FROM kb_chunks WHERE doc_id=?", (did,))
        c.execute("DELETE FROM kb_docs WHERE id=?", (did,))
    shutil.rmtree(_store_dir(cfgmod.load()) / did, ignore_errors=True)
    return True


# ---------- tìm kiếm
def _terms(query: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", fold(query)) if len(w) > 1][:12]


def _keyword_hits(query: str, k: int) -> list[int]:
    terms = _terms(query)
    if not terms:
        return []
    with db() as c:
        if _fts(c):
            try:
                q = " OR ".join(f'"{t}"' for t in terms)
                return [r["chunk_id"] for r in c.execute("SELECT chunk_id FROM kb_fts WHERE kb_fts MATCH ? ORDER BY rank LIMIT ?", (q, k))]
            except Exception:  # noqa: BLE001
                pass
        rows = c.execute("SELECT id, text FROM kb_chunks").fetchall()
    scored = [(sum(fold(r["text"]).count(t) for t in terms), r["id"]) for r in rows]
    return [cid for s, cid in sorted(scored, reverse=True)[:k] if s > 0]


def _vector_hits(query: str, k: int) -> list[int]:
    cfg = cfgmod.load()
    try:
        e = embeddings.get_embedder(cfg)
        if e is None:
            return []
        vecs, model = e.embed([query])
        with db() as c:
            rows = c.execute("SELECT chunk_id, dim, vec FROM kb_vecs WHERE model=?", (model,)).fetchall()
        rows = [r for r in rows if r["dim"] == len(vecs[0])]
        with db() as c:
            total = c.execute("SELECT COUNT(*) n FROM kb_chunks").fetchone()["n"]
        if len(rows) < total:  # còn đoạn chưa có vector của model này: nhúng nền để lần hỏi sau tìm theo nghĩa được đầy đủ
            _spawn(ensure_vectors)
        if not rows:
            return []
        import numpy as np
        m = np.vstack([np.frombuffer(r["vec"], dtype=np.float32) for r in rows])
        q = np.asarray(vecs[0], dtype=np.float32)
        s = m @ q / ((np.linalg.norm(m, axis=1) * (np.linalg.norm(q) or 1.0)) + 1e-12)
        order = [i for i in np.argsort(-s)[:k] if s[i] > 0.2]
        return [rows[i]["chunk_id"] for i in order]
    except Exception as ex:  # noqa: BLE001 - lùi về từ khóa
        log.info("vector search không khả dụng: %s", ex)
        return []


def search(query: str, limit: int = 6) -> list[dict]:
    """Gộp từ khóa và ngữ nghĩa bằng reciprocal-rank fusion; mỗi kết quả kèm tên file và vị trí."""
    ensure_schema()
    limit = max(1, min(int(limit), 15))
    score: dict[int, float] = {}
    how: dict[int, set[str]] = {}
    for label, ids in (("từ khóa", _keyword_hits(query, limit * 3)), ("ngữ nghĩa", _vector_hits(query, limit * 3))):
        for rank, cid in enumerate(ids):
            score[cid] = score.get(cid, 0.0) + 1.0 / (RRF_K + rank)
            how.setdefault(cid, set()).add(label)
    top = sorted(score, key=lambda c: -score[c])[:limit]
    if not top:
        return []
    with db() as c:
        q = ",".join("?" * len(top))
        rows = {r["id"]: r for r in c.execute(f"SELECT c.id, c.loc, c.text, d.id AS doc_id, d.name FROM kb_chunks c JOIN kb_docs d ON d.id=c.doc_id WHERE c.id IN ({q})", top)}
    return [{"doc_id": rows[i]["doc_id"], "name": rows[i]["name"], "loc": rows[i]["loc"], "text": rows[i]["text"], "score": round(score[i], 4), "how": sorted(how[i])} for i in top if i in rows]


def overview(focus: str, per_doc: int = 3, limit: int = 16) -> list[dict]:
    """Cho chế độ phân tích: phần mở đầu của từng tài liệu (để nắm tổng thể) cộng các đoạn khớp nhất với trọng tâm người dùng nêu."""
    ensure_schema()
    out, seen = [], set()
    with db() as c:
        rows = c.execute("SELECT c.id, c.loc, c.text, d.id AS doc_id, d.name FROM kb_chunks c JOIN kb_docs d ON d.id=c.doc_id "
                         "WHERE d.status='ready' AND c.ord < ? ORDER BY d.added DESC, c.doc_id, c.ord", (per_doc,)).fetchall()
    for r in rows:
        out.append({"doc_id": r["doc_id"], "name": r["name"], "loc": r["loc"], "text": r["text"]})
        seen.add((r["doc_id"], r["loc"], r["text"][:40]))
    for h in search(focus, 10) if focus.strip() else []:
        if (h["doc_id"], h["loc"], h["text"][:40]) not in seen:
            out.append(h)
    return out[:limit]


def stats() -> dict:
    ensure_schema()
    with db() as c:
        r = c.execute("SELECT COUNT(*) docs, COALESCE(SUM(chunks),0) chunks FROM kb_docs WHERE status='ready'").fetchone()
        pending = c.execute("SELECT COUNT(*) n FROM kb_docs WHERE status='indexing'").fetchone()["n"]
    return {"docs": r["docs"], "chunks": r["chunks"], "indexing": pending}
