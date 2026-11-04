"""Chạy thử bản server đã đóng gói: khởi động, gọi /api/health và trang chủ, rồi tắt. Dùng trong CI và khi build tay.

  python app/desktop/smoke_test.py app/desktop/build/argus-server
"""
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path


def main(folder: str) -> int:
    exe = Path(folder) / ("argus-server.exe" if os.name == "nt" else "argus-server")
    if not exe.exists():
        print(f"không thấy {exe}")
        return 1
    with tempfile.TemporaryDirectory() as home:
        proc = subprocess.Popen([str(exe), "--port", "0"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env={**os.environ, "ARGUS_HOME": home})
        try:
            port, deadline, log = None, time.time() + 90, []
            while time.time() < deadline and port is None:
                line = proc.stdout.readline()
                if not line and proc.poll() is not None:
                    break
                log.append(line)
                if m := re.search(r"ARGUS_READY (\d+)", line):
                    port = int(m.group(1))
            if port is None:
                print("server không báo sẵn sàng:\n" + "".join(log)[-3000:])
                return 1
            base = f"http://127.0.0.1:{port}"
            health = urllib.request.urlopen(f"{base}/api/health", timeout=10).read().decode()
            page = urllib.request.urlopen(base, timeout=10).read().decode()
            ok = '"ok"' in health.replace(" ", "") and "<div id=\"root\"" in page
            print("health:", health.strip()[:120], "| trang chủ:", "OK" if ok else "THIẾU giao diện web")
            return 0 if ok else 1
        finally:
            proc.terminate()
            try:
                proc.wait(10)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "app/desktop/build/argus-server"))
