# Argus Agent Desktop

Ứng dụng desktop (Electron) bọc server Argus đã đóng gói. Xem `docs/kien-truc.md` mục "Ứng dụng desktop".

Dựng tay trên Linux (từ thư mục gốc repo):

```bash
(cd app/frontend && npm ci && npm run build)
.venv/bin/pip install -e app/backend pyinstaller
.venv/bin/pyinstaller --noconfirm --distpath app/desktop/build --workpath app/desktop/build/work app/desktop/argus-server.spec
.venv/bin/python app/desktop/smoke_test.py app/desktop/build/argus-server     # kiểm tra nhanh bản server
(cd app/desktop && npm install && npx electron-builder --linux)               # ra file trong app/desktop/dist/
```

Chạy thử từ mã nguồn, không đóng gói: `cd app/desktop && npm install && npm start` (dùng `.venv` của repo).
Bản Windows chỉ dựng được trên Windows (CI: `.github/workflows/desktop.yml`).
