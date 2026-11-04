# Tài liệu dòng lệnh `argus`

Tất cả những gì làm được trên giao diện web đều làm được bằng dòng lệnh. Tài liệu này liệt kê từng lệnh, tùy chọn và ví dụ. Bạn cũng xem được trợ giúp ngay trong terminal bằng `argus <lệnh> --help`.

Xem thêm: [Hướng dẫn sử dụng](huong-dan-su-dung.md) · [Kiến trúc hệ thống](kien-truc.md).

## Mục lục

- [Tùy chọn chung](#tùy-chọn-chung)
- [Vận hành server](#vận-hành-server): `start`, `stop`, `restart`, `status`, `logs`, `open`, `dev`
- [Cài đặt và chẩn đoán](#cài-đặt-và-chẩn-đoán): `onboard`, `doctor`, `config`
- [Dùng agent](#dùng-agent): `chat`, `run`, `tasks`
- [Kỹ năng](#skills): `skills`
- [Bộ nhớ](#memory): `memory`
- [Tích hợp](#tích-hợp): `token`, `service`
- [Dữ liệu và bảo mật](#dữ-liệu-và-bảo-mật): `backup`, `restore`, `secrets`
- [Biến môi trường](#biến-môi-trường)
- [Mã thoát](#mã-thoát)
- [Công thức hay dùng](#công-thức-hay-dùng)

---

## Tùy chọn chung

```
argus [-h] [--version] [--lang {vi,en}] <lệnh> ...
```

| Tùy chọn | Ý nghĩa |
|---|---|
| `-h`, `--help` | Hiện trợ giúp (dùng được ở mọi lệnh con) |
| `--version` | Hiện phiên bản |
| `--lang {vi,en}` | Ngôn ngữ của CLI. Mặc định theo cấu hình hoặc hệ thống. Có thể đặt bằng biến `ARGUS_LANG` |

`--lang` đứng **trước** tên lệnh: `argus --lang en doctor`.

Cài đặt lệnh `argus`: `.venv/bin/pip install -e app/backend`, rồi thêm `.venv/bin` vào `PATH`. Nếu chưa muốn thêm vào `PATH`, gọi `.venv/bin/argus ...` hoặc `.venv/bin/python -m argus ...`.

---

## Vận hành server

### `argus start`

Khởi động server ở nền (daemon). Lần đầu, nếu giao diện web chưa build và máy có Node.js, lệnh tự build (khoảng 1 phút).

```
argus start [--host HOST] [--port PORT] [-f] [--no-build]
```

| Tùy chọn | Ý nghĩa |
|---|---|
| `--host HOST` | Địa chỉ lắng nghe. Mặc định `127.0.0.1` (chỉ máy này). `0.0.0.0` để mở cho mạng LAN, **khi đó hãy đặt mật khẩu giao diện** |
| `--port PORT` | Cổng. Mặc định `8787` |
| `-f`, `--foreground` | Chạy ở foreground (không tách nền), tiện khi debug hoặc dùng trong container |
| `--no-build` | Không tự build giao diện |

```bash
argus start                  # chạy nền ở 127.0.0.1:8787
argus start -f               # chạy foreground, Ctrl+C để dừng
argus start --port 9000
```

### `argus stop`

Dừng server đang chạy nền.

### `argus restart`

Dừng rồi khởi động lại. Nhận `--host` và `--port` như `start`. Dùng sau khi cập nhật mã nguồn.

### `argus status`

Hiện trạng thái: server có chạy không, địa chỉ, phiên bản, mô hình mặc định, số kỹ năng, Telegram, heartbeat, mật khẩu, sandbox, thư mục dữ liệu.

```
argus status [--json]
```

`--json` in dạng JSON để dùng trong script.

### `argus logs`

```
argus logs [-f] [-n N]
```

| Tùy chọn | Ý nghĩa |
|---|---|
| `-f`, `--follow` | Theo dõi log theo thời gian thực |
| `-n N` | Số dòng cuối cần in |

Log nằm ở `user-data/data/server.log`.

### `argus open`

Mở giao diện web bằng trình duyệt mặc định. Nhận `--host` và `--port`.

### `argus dev`

Chế độ phát triển: chạy backend tự nạp lại khi sửa code cùng máy chủ phát triển của giao diện. Cần Node.js và thư mục `app/frontend/`.

```
argus dev [--port PORT]
```

---

## Cài đặt và chẩn đoán

### `argus onboard`

Trình hướng dẫn cài đặt lần đầu. Ở chế độ tương tác, dùng **mũi tên lên/xuống** để di chuyển, **Space** để đánh dấu, **Enter** để chọn. Nó hỏi: ngôn ngữ, tên, mô hình AI (có thử kết nối), tùy chọn an toàn (sandbox Docker, mật khẩu), Telegram, heartbeat và dịch vụ tự khởi động.

```
argus onboard [--non-interactive] [--language {vi,en}] [--name NAME]
              [--provider PROVIDER] [--model MODEL] [--base-url BASE_URL]
              [--api-key-env API_KEY_ENV] [--api-key-stdin] [--skip-test]
              [--sandbox {none,docker}] [--password-env PASSWORD_ENV]
              [--telegram-token-env TELEGRAM_TOKEN_ENV]
              [--start | --no-start] [--heartbeat] [--service]
```

| Tùy chọn | Ý nghĩa |
|---|---|
| `--non-interactive` | Không hỏi gì, chỉ dùng các tùy chọn bên dưới (để chạy trong script, CI, Docker) |
| `--language {vi,en}` | Ngôn ngữ |
| `--name NAME` | Tên của bạn |
| `--provider PROVIDER` | Mẫu dịch vụ: `ollama`, `gemini`, `openai`, `anthropic`, `openrouter`, `deepseek`, `mistral`, `groq`, `xai`, `lmstudio`, `claude-code`, `antigravity`, `codex`, `custom` (ba mẫu cuối nhóm CLI dùng tài khoản đã đăng nhập, không cần API key; onboard chỉ kiểm tra lệnh có trong `PATH`) |
| `--model MODEL` | Tên model |
| `--base-url BASE_URL` | Địa chỉ API (cho `custom` hoặc ghi đè mẫu) |
| `--api-key-env NAME` | Tên biến môi trường chứa khóa API |
| `--api-key-stdin` | Đọc khóa API từ stdin (không để lộ trong lịch sử shell) |
| `--skip-test` | Không thử kết nối mô hình |
| `--sandbox {none,docker}` | Chạy lệnh shell trực tiếp hay trong Docker |
| `--password-env NAME` | Biến môi trường chứa mật khẩu giao diện |
| `--telegram-token-env NAME` | Biến môi trường chứa token bot Telegram |
| `--start` / `--no-start` | Có khởi động server ngay sau khi xong không |
| `--heartbeat` | Bật heartbeat |
| `--service` | Cài dịch vụ tự khởi động cùng máy |

```bash
# Cài tự động với Gemini, khóa lấy từ biến môi trường
export GEMINI_API_KEY=...
argus onboard --non-interactive --language vi --name Huy \
  --provider gemini --api-key-env GEMINI_API_KEY --start

# Cài với Antigravity (hoặc codex, claude-code) đã đăng nhập sẵn, không cần API key
argus onboard --non-interactive --provider antigravity --start

# Cài với Ollama chạy sẵn trên máy
argus onboard --non-interactive --provider ollama --model qwen2.5:3b --start

# Truyền khóa qua stdin
echo "$KEY" | argus onboard --non-interactive --provider openai --api-key-stdin
```

### `argus doctor`

Chẩn đoán toàn bộ hệ thống và gợi ý cách sửa. Chia theo nhóm: **Environment** (Python, gói, Node, giao diện đã build), **Data** (thư mục dữ liệu, dung lượng trống, config, quyền file, khóa bí mật, sao lưu, cơ sở dữ liệu, FTS5, workspace), **Server**, **Models** (kết nối từng mô hình), **Tools & integrations** (Docker, MCP, Telegram, kỹ năng) và **Extended features** (trình duyệt, trí nhớ ngữ nghĩa, tạo ảnh, xem ảnh, điều khiển máy tính, và các module công cụ nạp lỗi).

```
argus doctor [--fix] [--offline] [--json]
```

| Tùy chọn | Ý nghĩa |
|---|---|
| `--fix` | Tự sửa những lỗi an toàn: sửa quyền `config.json` và `master.key` về 600, tạo workspace và `SOUL.md` còn thiếu, build giao diện web nếu chưa có |
| `--offline` | Bỏ qua các kiểm tra cần mạng (gọi mô hình, Telegram) và việc khởi chạy thử trình duyệt |
| `--json` | In kết quả dạng JSON |

Với mô hình dùng CLI, doctor chỉ kiểm tra lệnh (`claude`…) có trong `PATH` chứ không gọi mô hình (tránh tốn lượt dùng). Mỗi dòng có biểu tượng: `✓` ổn, `!` cảnh báo, `✗` lỗi, `·` thông tin. Mã thoát là 1 nếu có lỗi (`✗`).

### `argus config`

```
argus config path        # in đường dẫn file config.json
argus config show        # in cấu hình (API key bị che)
```

---

## Dùng agent

### `argus chat`

Trò chuyện với agent ngay trong terminal.

```
argus chat [-s SESSION] [-p PROVIDER] [--permission {default,readonly,guarded,full}]
           [--effort {auto,low,medium,high}]
```

| Tùy chọn | Ý nghĩa |
|---|---|
| `-s`, `--session ID` | Mở lại một hội thoại theo id |
| `-p`, `--provider NAME` | Dùng mô hình này thay cho mặc định |
| `--permission MODE` | Quyền: `default`, `readonly` (chỉ đọc), `guarded` (hỏi trước mỗi lần ghi/chạy), `full` (toàn quyền) |
| `--effort LEVEL` | Mức nỗ lực suy nghĩ |

Lệnh gạch chéo trong phiên chat:

| Lệnh | Tác dụng |
|---|---|
| `/help` | Hiện trợ giúp |
| `/new` | Bắt đầu hội thoại mới |
| `/sessions` | Liệt kê hội thoại gần đây |
| `/open <id>` | Mở lại một hội thoại |
| `/model <tên>` | Đổi mô hình |
| `/perm <chế độ>` | Đổi quyền (`default`, `readonly`, `guarded`, `full`) |
| `/effort <mức>` | Đổi mức nỗ lực (`auto`, `low`, `medium`, `high`) |
| `/skills` | Liệt kê kỹ năng |
| `/files` | Liệt kê file của hội thoại |
| `/exit` | Thoát (hoặc Ctrl+D) |

Khi agent cần xin phép (ví dụ chạy lệnh), terminal hỏi `y/N` và hiện đúng lệnh sẽ chạy.

### `argus run`

Chạy **một yêu cầu rồi thoát**, hợp cho script, cron, CI. Mặc định **không có người duyệt**, nên mọi lệnh shell bị từ chối trừ khi bạn nói khác.

```
argus run [-s SESSION] [-p PROVIDER] [--permission MODE] [--effort LEVEL]
          [--exec-policy {deny,allow,allowlist}] [--allow CMD] [--ask]
          [--tools TOOLS] [--timeout SECONDS] [--json] [-v]
          prompt
```

| Tùy chọn | Ý nghĩa |
|---|---|
| `prompt` | Nội dung yêu cầu. Dùng `-` để đọc từ stdin |
| `-s`, `--session ID` | Chạy tiếp trong một hội thoại có sẵn |
| `-p`, `--provider NAME` | Chọn mô hình |
| `--permission MODE` | Như `chat` |
| `--effort LEVEL` | Như `chat` |
| `--exec-policy` | Chính sách cho lệnh shell khi không có người: `deny` (mặc định, từ chối hết), `allow` (cho hết), `allowlist` (chỉ các lệnh khớp `--allow`) |
| `--allow CMD` | Tiền tố lệnh được phép khi dùng `allowlist`. Lặp lại được nhiều lần |
| `--ask` | Hỏi `y/N` tương tác thay vì dùng chính sách (cần terminal) |
| `--tools a,b,c` | Chỉ cho phép các công cụ này trong lượt chạy |
| `--timeout N` | Giới hạn thời gian, giây |
| `--json` | In kết quả dạng JSON (gồm `output`, `error`…) |
| `-v`, `--verbose` | In thêm các bước công cụ ra stderr |

```bash
argus run "Tóm tắt file notes.md trong 5 gạch đầu dòng"

# Đọc yêu cầu từ stdin, chỉ cho phép vài công cụ, kết quả JSON
cat yeu-cau.txt | argus run - --tools read,list_dir,web_search --json

# Cho phép riêng lệnh git status và git log
argus run "Cho tôi biết repo này gần đây đổi gì" \
  --exec-policy allowlist --allow "git status" --allow "git log"

# Chạy trong ngữ cảnh một hội thoại cũ
argus run "Làm tiếp bước 2" -s 9dbf1f77
```

### `argus tasks`

Việc chạy nền và agent con (giống trang **Tác vụ** trên web).

```
argus tasks list   [--status S] [--kind K] [--limit N] [--json]
argus tasks show   <id> [--json]
argus tasks cancel <id>
argus tasks run    <mục tiêu> [--role ROLE] [--permission MODE] [--provider NAME]
```

| Lệnh | Ý nghĩa |
|---|---|
| `list` | Liệt kê. `--status` lọc theo `queued`, `running`, `done`, `failed`, `cancelled`, `interrupted`. `--kind` lọc `task` (việc nền) hoặc `subagent` (agent con) |
| `show <id>` | Chi tiết, tiến độ, kết quả hoặc lỗi |
| `cancel <id>` | Yêu cầu dừng một việc đang chạy. Việc đang chạy ở server nhận lệnh trong vòng vài giây |
| `run <mục tiêu>` | Chạy việc **ngay trong tiến trình CLI** (Ctrl+C để dừng). Khác với giao diện web, CLI không giữ việc sống sau khi thoát |

Với `run`: `--role` là `general` hoặc tên vai trò (`researcher`, `coder`, `reviewer`, hoặc vai trò bạn tự thêm). `--permission` là `readonly`, `default` (mặc định: tạo file trong thư mục làm việc, từ chối việc nguy hiểm), `guarded` hoặc `full`. Lưu ý `guarded` hỏi cả khi ghi file, mà việc nền không có người duyệt nên mọi lần ghi sẽ bị từ chối.

```bash
argus tasks run "Tìm 3 bài báo mới nhất về RAG và viết tóm tắt vào report.md" --role researcher
argus tasks list --status running
argus tasks show 7a1c93e0
argus tasks cancel 7a1c93e0
```

---

## Skills

Quản lý kỹ năng, gồm cài từ **ClawHub**.

```
argus skills list   [--json]
argus skills search <từ khóa> [-n LIMIT] [--json]
argus skills install <chủ>/<tên> [-y] [--overwrite]
argus skills remove  <tên> [-y]
argus skills update  [tên]
```

| Lệnh | Ý nghĩa |
|---|---|
| `list` | Các kỹ năng đã cài, cho biết kỹ năng nào dùng được, kỹ năng nào còn thiếu điều kiện |
| `search` | Tìm trên ClawHub |
| `install <chủ>/<tên>` | Cài. Hiện cảnh báo bảo mật nếu đáng ngờ và hỏi xác nhận; `-y` bỏ qua câu hỏi, `--overwrite` ghi đè bản đã có |
| `remove <tên>` | Gỡ một kỹ năng trong workspace |
| `update [tên]` | Cập nhật kỹ năng cài từ ClawHub (một cái hoặc tất cả) |

```bash
argus skills search "pdf"
argus skills install someowner/pdf-reader
argus skills update
```

> Đọc `SKILL.md` của kỹ năng trước khi cài. Kỹ năng có thể bảo agent chạy lệnh.

---

## Memory

Trí nhớ theo nghĩa và dọn `MEMORY.md` bằng AI.

```
argus memory status  [--json]
argus memory search  <từ khóa...> [-n LIMIT]
argus memory reindex
argus memory curate  [--apply] [--provider NAME]
```

| Lệnh | Ý nghĩa |
|---|---|
| `status` | Backend embedding đang dùng (`hash`, `ollama`, `openai`), model, số chiều, có kết nối được không, số vector đã lưu, số ghi chú |
| `search <từ khóa>` | Tìm trong hội thoại cũ và `MEMORY.md`, kết hợp tìm từ khóa và tìm theo nghĩa. Mỗi dòng ghi rõ khớp theo từ khóa hay theo ngữ nghĩa |
| `reindex` | Nhúng lại toàn bộ (cần sau khi đổi model embedding). Hiện tiến độ |
| `curate` | AI đề xuất bản `MEMORY.md` gọn hơn. **Mặc định chỉ in khác biệt (diff), không ghi gì**. Thêm `--apply` để ghi thật; bản cũ được lưu thành `MEMORY.md.bak-<giờ>` |

Backend embedding chọn trong `config.json` mục `memory` hoặc ở giao diện (Cài đặt → Tính năng). Chế độ `hash` chỉ khớp theo từ gần giống; muốn hiểu nghĩa thật hãy dùng `openai` (Gemini/OpenAI) hoặc một model embedding trên Ollama.

```bash
argus memory status
argus memory search "người tôi hay họp cùng"
argus memory curate                # xem trước
argus memory curate --apply        # áp dụng
```

---

## Tích hợp

### `argus token`

Quản lý API token cho ứng dụng ngoài gọi `/v1/*`.

```
argus token create <tên> [--allow-exec] [--json]
argus token list
argus token revoke <id>
```

| Tùy chọn | Ý nghĩa |
|---|---|
| `create <tên>` | Tạo token. Token đầy đủ (dạng `agt_...`) **chỉ hiện một lần**, hãy lưu lại |
| `--allow-exec` | Cho phép token này dùng `exec_policy` là `allow` hoặc `allowlist` (chạy lệnh shell). Mặc định không |
| `--json` | In kết quả dạng JSON |
| `list` | Liệt kê token (chỉ hiện tiền tố, không hiện token đầy đủ) |
| `revoke <id>` | Thu hồi |

```bash
argus token create ci-bot --json
curl -s http://127.0.0.1:8787/v1/status -H "Authorization: Bearer agt_xxxxxxxx"
```

### `argus service`

Chạy Argus như dịch vụ tự khởi động cùng máy: **systemd** (user service) trên Linux, **launchd** trên macOS.

```
argus service install [--host HOST] [--port PORT] [--dry-run]
argus service uninstall | start | stop | restart | status
```

`install` tự sinh file dịch vụ với đúng đường dẫn trên máy bạn rồi bật nó. `--dry-run` chỉ in file sẽ tạo mà không cài. Để dịch vụ chạy cả khi bạn chưa đăng nhập (Linux): `loginctl enable-linger $USER`.

---

## Dữ liệu và bảo mật

### backup

Sao lưu cấu hình, cơ sở dữ liệu và workspace thành một file `.tar.gz`.

```
argus backup [-o FILE] [--include-key] [--no-sessions] [--encrypt] [--passphrase-env NAME]
```

| Tùy chọn | Ý nghĩa |
|---|---|
| `-o`, `--output FILE` | File đích. Mặc định `user-data/backups/argus-backup-<giờ>.tar.gz` |
| `--include-key` | Đưa cả **khóa chủ** vào bản sao lưu để khôi phục được trên máy khác. **Luôn dùng cùng `--encrypt`** |
| `--no-sessions` | Bỏ file của từng hội thoại (`workspace/sessions`) cho nhẹ |
| `--encrypt` | Mã hóa bản sao lưu bằng mật khẩu (AES-GCM) |
| `--passphrase-env NAME` | Đọc mật khẩu từ biến môi trường thay vì hỏi |

```bash
argus backup                                   # nhanh, giữ ở máy
argus backup --include-key --encrypt           # đầy đủ, mang sang máy khác
BK_PASS=... argus backup --encrypt --passphrase-env BK_PASS -o /mnt/usb/argus.tar.gz.enc
```

### restore

```
argus restore <file> [--force] [--passphrase-env NAME] [--master-key-file FILE]
```

| Tùy chọn | Ý nghĩa |
|---|---|
| `<file>` | File sao lưu (`.tar.gz` hoặc `.tar.gz.enc`) |
| `--force` | Ghi đè dữ liệu hiện có. **Dữ liệu hiện tại được sao lưu trước** rồi mới ghi đè |
| `--passphrase-env NAME` | Mật khẩu giải mã lấy từ biến môi trường |
| `--master-key-file FILE` | File khóa chủ, dùng khi bản sao lưu không kèm khóa chủ |

Khôi phục kiểm tra kỹ nội dung (chặn đường dẫn thoát ra ngoài và liên kết tượng trưng độc hại) trước khi ghi. Nếu thiếu khóa chủ, các khóa API đã mã hóa không đọc lại được và bạn phải nhập lại.

### secrets

Mã hóa các khóa bí mật (API key, token Telegram, biến môi trường/header MCP, khóa kỹ năng) trong `config.json`. Việc mã hóa được bật sẵn; nhóm lệnh này để kiểm tra và quản lý khóa chủ.

```
argus secrets status | encrypt | decrypt | keychain | file | rotate
```

| Lệnh | Ý nghĩa |
|---|---|
| `status` | Bao nhiêu khóa đã mã hóa, còn bao nhiêu ở dạng chữ thường, khóa chủ lưu ở đâu (`env`, `keychain`, `file`) |
| `encrypt` | Mã hóa mọi khóa còn ở dạng chữ thường |
| `decrypt` | Ghi các khóa ra dạng chữ thường. **Không khuyên dùng** |
| `keychain` | Chuyển khóa chủ vào kho khóa của hệ điều hành (cần `pip install keyring`) |
| `file` | Chuyển khóa chủ về file `user-data/data/master.key` (quyền 600) |
| `rotate` | Đổi khóa chủ và mã hóa lại tất cả |

Khóa chủ được lấy theo thứ tự: biến môi trường `ARGUS_MASTER_KEY` → keychain → file `master.key`.

---

## Biến môi trường

Mọi biến đều có tiền tố `ARGUS_`. Tiền tố cũ `AGENT_` vẫn được nhận để không làm hỏng cấu hình đã có.

| Biến | Ý nghĩa |
|---|---|
| `ARGUS_HOME` | Thư mục dữ liệu cá nhân. Mặc định `<repo>/user-data` |
| `ARGUS_CONFIG` | Đường dẫn tới `config.json` (Docker đặt là `/app/data/config.json`) |
| `ARGUS_TEMPLATE` | Thư mục workspace mẫu dùng để tạo workspace lần đầu |
| `ARGUS_MASTER_KEY` | Khóa chủ để giải mã khóa bí mật (ưu tiên cao nhất) |
| `ARGUS_ENCRYPT` | Đặt `0` để tắt mã hóa khóa bí mật |
| `ARGUS_LANG` | Ngôn ngữ CLI (`vi` hoặc `en`) |
| `ARGUS_URL` | Địa chỉ server cho `app/backend/argus/mcp_server.py` (mặc định `http://127.0.0.1:8787`) |
| `ARGUS_TOKEN` | API token cho `mcp_server.py` |
| `ARGUS_ALLOWED_HOSTS` | Danh sách tên máy chủ (cách nhau bằng dấu phẩy) được phép truy cập, ngoài `127.0.0.1` và `localhost`. Cần khi đặt sau proxy hoặc dùng tên miền |
| `ARGUS_DEV_ORIGINS` | Danh sách origin được phép ở chế độ phát triển |
| `ARGUS_DEBUG` | Bật ghi log chi tiết |

---

## Mã thoát

| Mã | Ý nghĩa |
|---|---|
| `0` | Thành công |
| `1` | Lỗi khi chạy (ví dụ `argus run` gặp lỗi từ mô hình, `argus doctor` thấy lỗi, không tìm thấy việc cần xem) |
| `2` | Dùng sai (thiếu yêu cầu, tùy chọn không hợp lệ, `--ask` khi không có terminal, chính sách lệnh không được phép) |

---

## Công thức hay dùng

**Cài một máy mới, không cần tương tác:**

```bash
python3 -m venv .venv && .venv/bin/pip install -e app/backend
(cd app/frontend && npm ci && npm run build)
export GEMINI_API_KEY=...
.venv/bin/argus onboard --non-interactive --provider gemini --api-key-env GEMINI_API_KEY --start --service
```

**Chạy một việc theo lịch bằng cron của hệ điều hành** (ngoài việc dùng trang Tự động hóa):

```cron
0 8 * * *  /đường/dẫn/.venv/bin/argus run "Tóm tắt tin công nghệ hôm nay" --tools web_search,web_fetch > /tmp/tin.txt
```

**Gọi agent từ script khác và lấy kết quả JSON:**

```bash
argus run "Liệt kê 3 việc cần làm hôm nay từ MEMORY.md" --tools read,memory_search --json | jq -r .output
```

**Kiểm tra sức khỏe trước khi triển khai:**

```bash
argus doctor --offline --json | jq '[.[] | select(.status=="fail")]'
```

**Sao lưu hằng đêm, mã hóa, kèm khóa chủ:**

```bash
BK_PASS="$(cat ~/.bk-pass)" argus backup --include-key --encrypt --passphrase-env BK_PASS -o ~/backups/argus-$(date +%F).tar.gz.enc
```
