"""Danh sach skill tren ClawHub duoc chon loc cho nguoi dung pho thong (van phong, hoc tap, doi song).

Chon tu bang xep hang tai nhieu nhat cua ClawHub; chi lay skill co mo ta ro rang, khong bi gan co dang ngo.
`needs`: key = can khoa API/tai khoan, cli = can cai them cong cu dong lenh, mac/linux = chi chay tren he dieu hanh do.
"""
import time
from concurrent.futures import ThreadPoolExecutor

from .clawhub import ClawHub, ClawHubError

CATEGORIES = [
    ("research", "Tìm hiểu & tin tức", "Research & news"),
    ("docs", "Văn bản & tài liệu", "Documents"),
    ("work", "Công việc & liên lạc", "Work & communication"),
    ("media", "Âm thanh, video & ảnh", "Audio, video & images"),
    ("data", "Dữ liệu & tài chính", "Data & finance"),
    ("life", "Đời sống & giải trí", "Daily life & fun"),
    ("safety", "An toàn", "Safety"),
]

# (owner, slug, category, vi, en, needs)
PICKS = [
    ("steipete", "weather", "research", "Xem thời tiết và dự báo, không cần khóa API.", "Current weather and forecasts, no API key.", []),
    ("joargp", "news-summary", "research", "Tóm tắt tin tức mỗi ngày từ các nguồn đáng tin.", "Daily news briefings from trusted sources.", []),
    ("parags", "deep-research-pro", "research", "Nghiên cứu sâu: tìm nhiều nguồn rồi tổng hợp thành báo cáo có trích dẫn.", "Deep research: searches many sources and writes a cited report.", []),
    ("jakelin", "ddg-web-search", "research", "Tìm kiếm web bằng DuckDuckGo, không cần khóa API.", "Web search through DuckDuckGo, no API key.", []),
    ("michaelgathara", "youtube-watcher", "research", "Đọc phụ đề video YouTube để tóm tắt hoặc hỏi đáp về nội dung.", "Read YouTube transcripts to summarize or ask about a video.", ["cli"]),

    ("ivangdavila", "word-docx", "docs", "Tạo, đọc và sửa tài liệu Word (.docx).", "Create, read and edit Word (.docx) documents.", []),
    ("ivangdavila", "excel-xlsx", "docs", "Tạo, đọc và sửa bảng tính Excel (.xlsx).", "Create, read and edit Excel (.xlsx) workbooks.", []),
    ("ivangdavila", "powerpoint-pptx", "docs", "Tạo, đọc và sửa bài thuyết trình PowerPoint (.pptx).", "Create, read and edit PowerPoint (.pptx) decks.", []),
    ("awspace", "pdf", "docs", "Làm việc với PDF: lấy chữ và bảng, gộp, tách, điền biểu mẫu.", "PDF toolkit: extract text and tables, merge, split, fill forms.", []),
    ("steipete", "nano-pdf", "docs", "Sửa nội dung PDF bằng câu lệnh tự nhiên.", "Edit PDFs with plain-language instructions.", ["cli"]),
    ("steipete", "markdown-converter", "docs", "Chuyển nhiều loại file (Word, PDF, HTML…) sang Markdown.", "Convert Word, PDF, HTML and more to Markdown.", ["cli"]),
    ("mkpareek0315", "summarize-pro", "docs", "Tóm tắt văn bản, bài báo, tài liệu, cuộc họp và email.", "Summarize text, articles, documents, meetings and email.", []),
    ("biostartechnology", "humanizer", "docs", "Làm bài viết do AI tạo ra tự nhiên hơn, bớt giọng máy móc.", "Make AI-written text sound more natural.", []),

    ("steipete", "gog", "work", "Gmail, Lịch, Drive, Danh bạ, Sheets và Docs của Google.", "Gmail, Calendar, Drive, Contacts, Sheets and Docs from Google.", ["cli", "key"]),
    ("steipete", "notion", "work", "Tạo và quản lý trang, cơ sở dữ liệu trong Notion.", "Create and manage Notion pages and databases.", ["key"]),
    ("steipete", "obsidian", "work", "Làm việc với ghi chú Obsidian (file Markdown thường).", "Work with Obsidian notes (plain Markdown vaults).", ["cli"]),
    ("lamelas", "himalaya", "work", "Đọc, viết, trả lời email qua IMAP/SMTP (mọi nhà cung cấp).", "Read, write and reply to email over IMAP/SMTP.", ["cli", "key"]),
    ("asleep123", "caldav-calendar", "work", "Xem và thêm lịch CalDAV (iCloud, Google, Fastmail, Nextcloud).", "Query and add CalDAV calendars (iCloud, Google, Fastmail, Nextcloud).", ["cli", "linux"]),
    ("steipete", "trello", "work", "Quản lý bảng, danh sách và thẻ công việc trên Trello.", "Manage Trello boards, lists and cards.", ["key"]),
    ("steipete", "apple-notes", "work", "Tạo và tìm Ghi chú của Apple.", "Create and search Apple Notes.", ["cli", "mac"]),
    ("steipete", "apple-reminders", "work", "Quản lý Lời nhắc của Apple.", "Manage Apple Reminders.", ["cli", "mac"]),

    ("steipete", "openai-whisper", "media", "Chuyển giọng nói thành văn bản ngay trên máy, không cần khóa API.", "Local speech-to-text, no API key.", ["cli"]),
    ("steipete", "video-frames", "media", "Cắt ảnh hoặc đoạn ngắn từ video.", "Extract frames or short clips from video.", ["cli"]),
    ("steipete", "nano-banana-pro", "media", "Tạo và chỉnh sửa ảnh bằng Gemini.", "Generate and edit images with Gemini.", ["key"]),

    ("ivangdavila", "data-analysis", "data", "Phân tích và vẽ biểu đồ dữ liệu, truy vấn cơ sở dữ liệu, tạo báo cáo.", "Analyze and chart data, query databases, build reports.", []),
    ("udiedrichsen", "stock-analysis", "data", "Phân tích cổ phiếu và tiền mã hóa bằng dữ liệu Yahoo Finance.", "Analyze stocks and crypto with Yahoo Finance data.", []),

    ("anotb", "homeassistant-skill", "life", "Xem và điều khiển nhà thông minh qua Home Assistant.", "Inspect and control your smart home through Home Assistant.", ["key"]),
    ("steipete", "spotify-player", "life", "Phát và tìm nhạc Spotify từ dòng lệnh.", "Play and search Spotify from the command line.", ["cli", "key"]),

    ("spclaudehome", "skill-vetter", "safety", "Kiểm tra độ an toàn của một skill trước khi cài.", "Vet a skill for safety before you install it.", []),
]

# Cach cai cong cu dong lenh ma mot so skill can (lenh lay tu phan install cua chinh skill, hoac cach cai chinh thuc cua cong cu).
# None = chua co lenh chuan cho he dieu hanh do: giao dien chi dan toi trang chu cua cong cu.
TOOLS = {
    "yt-dlp": {"mac": "brew install yt-dlp", "linux": "pipx install yt-dlp", "windows": "winget install yt-dlp.yt-dlp", "url": "https://github.com/yt-dlp/yt-dlp"},
    "ffmpeg": {"mac": "brew install ffmpeg", "linux": "sudo apt install ffmpeg", "windows": "winget install Gyan.FFmpeg", "url": "https://ffmpeg.org/download.html"},
    "nano-pdf": {"mac": "uv tool install nano-pdf", "linux": "uv tool install nano-pdf", "windows": "uv tool install nano-pdf", "url": "https://pypi.org/project/nano-pdf/"},
    "markitdown": {"mac": "pipx install markitdown", "linux": "pipx install markitdown", "windows": "pipx install markitdown", "url": "https://github.com/microsoft/markitdown"},
    "whisper": {"mac": "brew install openai-whisper", "linux": "pipx install openai-whisper", "windows": "pip install -U openai-whisper", "url": "https://github.com/openai/whisper"},
    "gog": {"mac": "brew install steipete/tap/gogcli", "linux": "brew install steipete/tap/gogcli", "windows": None, "url": "https://gogcli.sh"},
    "obsidian-cli": {"mac": "brew install yakitrak/yakitrak/obsidian-cli", "linux": "brew install yakitrak/yakitrak/obsidian-cli", "windows": None, "url": "https://github.com/Yakitrak/obsidian-cli"},
    "himalaya": {"mac": "brew install himalaya", "linux": "brew install himalaya", "windows": "scoop install himalaya", "url": "https://github.com/pimalaya/himalaya"},
    "vdirsyncer": {"mac": "brew install vdirsyncer", "linux": "sudo apt install vdirsyncer", "windows": None, "url": "https://vdirsyncer.pimutils.org"},
    "khal": {"mac": "brew install khal", "linux": "sudo apt install khal", "windows": None, "url": "https://khal.readthedocs.io"},
    "memo": {"mac": "brew install antoniorodr/memo/memo", "linux": None, "windows": None, "url": "https://github.com/antoniorodr/memo"},
    "remindctl": {"mac": "brew install steipete/tap/remindctl", "linux": None, "windows": None, "url": "https://github.com/steipete/remindctl"},
    "spogo": {"mac": "brew install steipete/tap/spogo", "linux": None, "windows": None, "url": "https://github.com/steipete/spogo"},
    "spotify_player": {"mac": "brew install spotify_player", "linux": "cargo install spotify_player", "windows": "cargo install spotify_player", "url": "https://github.com/aome510/spotify-player"},
}
# slug -> lenh can co (hien huong dan cai tren the goi y)
BINS = {'youtube-watcher': ['yt-dlp'], 'nano-pdf': ['nano-pdf'], 'markdown-converter': ['markitdown'], 'gog': ['gog'], 'obsidian': ['obsidian-cli'], 'himalaya': ['himalaya'], 'caldav-calendar': ['vdirsyncer', 'khal'], 'apple-notes': ['memo'], 'apple-reminders': ['remindctl'], 'openai-whisper': ['whisper'], 'video-frames': ['ffmpeg'], 'spotify-player': ['spogo']}

_cache: dict[str, tuple[float, dict]] = {}
TTL = 3600


def _stats(hub: ClawHub, owner: str, slug: str) -> dict:
    key = f"{owner}/{slug}"
    if key in _cache and _cache[key][0] > time.time():
        return _cache[key][1]
    try:
        d = hub.detail(slug, owner)
        out = {"name": d["name"], "downloads": d["downloads"], "version": d["version"], "installable": d["installable"],
               "flagged": bool((d.get("moderation") or {}).get("isSuspicious") or (d.get("moderation") or {}).get("isMalwareBlocked"))}
    except (ClawHubError, KeyError):
        return {}
    _cache[key] = (time.time() + TTL, out)
    return out


def picks(hub: ClawHub) -> dict:
    """Danh sach goi y kem so luot tai moi nhat tu ClawHub (loi mang thi van tra ve danh sach tinh)."""
    with ThreadPoolExecutor(max_workers=8) as pool:
        live = list(pool.map(lambda p: _stats(hub, p[0], p[1]), PICKS))
    items = []
    for (owner, slug, cat, vi, en, needs), st in zip(PICKS, live):
        if st.get("flagged"):
            continue
        items.append({"owner": owner, "slug": slug, "category": cat, "vi": vi, "en": en, "needs": needs, "bins": BINS.get(slug, []), "name": st.get("name") or slug,
                      "downloads": st.get("downloads", 0), "version": st.get("version"), "installable": st.get("installable", True)})
    return {"categories": [{"id": i, "vi": v, "en": e} for i, v, e in CATEGORIES], "items": items, "tools": TOOLS}
