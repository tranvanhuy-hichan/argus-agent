# PyInstaller: đóng gói server Argus (Python + giao diện web + mẫu workspace) thành thư mục tự chứa.
#   pyinstaller --noconfirm --distpath build --workpath build/work app/desktop/argus-server.spec
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

APP = Path(SPECPATH).resolve().parent          # <repo>/app
datas, binaries, hidden = [], [], collect_submodules("argus")
# mcp.cli cần typer (không dùng) nên bỏ khỏi phần tự dò
hidden += collect_submodules("mcp", filter=lambda n: not n.startswith("mcp.cli"))
datas += collect_data_files("mcp")
for pkg in ("playwright", "uvicorn", "croniter"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hidden += h
hidden += ["uvicorn.logging", "uvicorn.loops.auto", "uvicorn.protocols.http.auto", "uvicorn.protocols.websockets.auto", "uvicorn.lifespan.on"]
datas += [(str(APP / "frontend" / "dist"), "frontend/dist"), (str(APP / "templates" / "workspace"), "templates/workspace")]

a = Analysis([str(Path(SPECPATH) / "server_entry.py")], pathex=[str(APP / "backend")], binaries=binaries, datas=datas,
             hiddenimports=hidden, excludes=["tkinter", "pytest"], noarchive=False)
pyz = PYZ(a.pure)
# utf8_mode: Windows mặc định cp1252 nên file tiếng Việt sẽ hỏng nếu thiếu
exe = EXE(pyz, a.scripts, [("X utf8_mode=1", None, "OPTION")], exclude_binaries=True, name="argus-server", console=True)
coll = COLLECT(exe, a.binaries, a.datas, name="argus-server")
