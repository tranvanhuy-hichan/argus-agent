# Hướng dẫn sử dụng Argus Agent

Tài liệu này dành cho người dùng, không cần biết lập trình. Nếu bạn muốn dùng dòng lệnh, xem [cli.md](cli.md). Nếu bạn muốn hiểu hoặc sửa mã nguồn, xem [kien-truc.md](kien-truc.md).

## Mục lục

1. [Argus Agent là gì](#1-argus-agent-là-gì)
2. [Cài đặt và chạy lần đầu](#2-cài-đặt-và-chạy-lần-đầu)
3. [Làm quen với giao diện](#3-làm-quen-với-giao-diện)
4. [Trò chuyện với agent](#4-trò-chuyện-với-agent)
5. [Giao việc dài: trang Tác vụ](#5-giao-việc-dài-trang-tác-vụ)
6. [Việc tự động theo lịch](#6-việc-tự-động-theo-lịch)
7. [Kỹ năng (Skills)](#7-kỹ-năng-skills)
8. [Mô hình AI](#8-mô-hình-ai)
9. [Kết nối: công cụ ngoài, Telegram, API](#9-kết-nối-công-cụ-ngoài-telegram-api)
10. [Tính cách và trí nhớ](#10-tính-cách-và-trí-nhớ)
11. [Các tính năng nâng cao](#11-các-tính-năng-nâng-cao)
12. [Thống kê và lịch sử](#12-thống-kê-và-lịch-sử)
13. [An toàn và quyền riêng tư](#13-an-toàn-và-quyền-riêng-tư)
14. [Sao lưu và khôi phục](#14-sao-lưu-và-khôi-phục)
15. [Xử lý sự cố](#15-xử-lý-sự-cố)

---

## 1. Argus Agent là gì

Argus Agent là một trợ lý AI cá nhân **chạy ngay trên máy của bạn**. Bạn trò chuyện với nó như với một người trợ lý: nó đọc và viết file, tìm thông tin trên web, mở trình duyệt, chạy lệnh (khi bạn cho phép), nhớ những điều quan trọng về bạn, và có thể làm việc ngầm hoặc theo lịch rồi báo kết quả qua Hộp thư hoặc Telegram.

Điểm cần nhớ:

- **Dữ liệu ở trên máy bạn.** Hội thoại, bộ nhớ, file và khóa API nằm trong thư mục `user-data/`. Argus không gửi chúng đi đâu, trừ nội dung hội thoại gửi tới mô hình AI mà bạn chọn (ví dụ Gemini). Nếu bạn dùng mô hình chạy trên máy (Ollama), không có gì rời khỏi máy.
- **Agent có "bộ não" là một mô hình AI.** Bạn chọn mô hình ở trang **Mô hình AI**. Có loại chạy trên máy (miễn phí) và loại đám mây (cần khóa API).
- **Bạn luôn nắm quyền.** Việc nguy hiểm như chạy lệnh hay ghi file ngoài thư mục làm việc đều hỏi bạn trước, trừ khi bạn chủ động chọn "Toàn quyền".

## 2. Cài đặt và chạy lần đầu

### Cách dành cho người dùng bình thường: ứng dụng desktop

Tải bản cài đặt ở trang **Releases** của dự án rồi cài như một phần mềm bình thường:

- **Windows:** chạy `Argus-Agent-<phiên bản>-win-x64.exe`. Cài một cú bấm, có shortcut ở Start Menu.
- **Linux:** `Argus-Agent-<phiên bản>-linux-x86_64.AppImage` (cấp quyền chạy rồi bấm đúp) hoặc gói `.deb` (`sudo apt install ./Argus-Agent-*.deb`).

Mở "Argus Agent" là có ngay cửa sổ riêng, không cần dòng lệnh, không cần cài Python. App tự chạy server bên trong và tự tắt khi bạn đóng cửa sổ. Dữ liệu (cấu hình, hội thoại, workspace) nằm ở thư mục dữ liệu của người dùng và **được giữ lại khi cập nhật hay gỡ cài đặt**: menu **Trợ giúp → Mở thư mục dữ liệu**. Nếu app không mở được, menu **Trợ giúp → Xem nhật ký**.

Bản desktop có dữ liệu riêng, tách khỏi bản chạy bằng CLI hay Docker trên cùng máy, nên hai bên không đụng nhau. Người dùng kỹ thuật vẫn cài và dùng `argus` như mô tả bên dưới.

### Cách dành cho người dùng kỹ thuật: CLI

Cần Python 3.11 trở lên (và Node 20 trở lên nếu muốn tự build giao diện).

```bash
git clone https://github.com/tranvanhuy-hichan/argus-agent.git
cd argus-agent
python3 -m venv .venv
.venv/bin/pip install -e app/backend
(cd app/frontend && npm install && npm run build)
.venv/bin/argus onboard
```

Lệnh cuối là **trình hướng dẫn cài đặt lần đầu**. Nó dùng phím mũi tên lên/xuống để chọn, Space để đánh dấu, Enter để xác nhận, và hỏi lần lượt:

1. Ngôn ngữ (Tiếng Việt hoặc English).
2. Tên của bạn.
3. Mô hình AI nào (Ollama, Gemini, OpenAI, Claude…) và khóa API nếu cần. Nó thử kết nối ngay để báo bạn biết khóa có dùng được không.
4. Các tùy chọn an toàn: có chạy lệnh trong Docker cách ly không, có đặt mật khẩu giao diện không.
5. Có kết nối Telegram không.
6. Có bật heartbeat (agent tự kiểm tra định kỳ) không, và có cài chế độ tự khởi động cùng máy không.

Xong, mở **http://127.0.0.1:8787** trong trình duyệt (hoặc gõ `argus open`).

> Mẹo: thêm `.venv/bin` vào `PATH` (hoặc chạy `source .venv/bin/activate`) để gõ ngắn `argus ...` thay vì `.venv/bin/argus ...`.

### Mỗi lần mở máy

| Bạn muốn | Làm gì |
|---|---|
| Chạy thủ công | `argus start` rồi `argus open` |
| Tự chạy mỗi khi bật máy | `argus service install` (làm một lần) |
| Kiểm tra có đang chạy không | `argus status` |
| Gặp lỗi lạ | `argus doctor` (chẩn đoán và gợi ý cách sửa) |

### Chạy bằng Docker

```bash
docker compose up -d --build
```

Mở http://127.0.0.1:8787. Dữ liệu cá nhân nằm ở `./user-data`. Muốn dùng Ollama đang chạy trên máy chủ từ trong container, đặt địa chỉ là `http://host.docker.internal:11434/v1`.

## 3. Làm quen với giao diện

Thanh bên trái gom các trang theo nhóm:

| Nhóm | Trang | Dùng để |
|---|---|---|
| (đầu) | **Trang chủ** | Xem tổng quan, ô gõ nhanh, danh sách việc nên làm tiếp để hoàn tất cài đặt |
| (đầu) | **Trò chuyện** | Nói chuyện và giao việc cho agent |
| **Công việc** | **Tác vụ** | Giao việc dài cho agent làm ngầm |
| | **Tự động hóa** | Việc lặp lại theo lịch (mỗi sáng 8 giờ…) |
| | **Hộp thư** | Thông báo agent gửi cho bạn |
| **Khả năng của agent** | **Kỹ năng** | Dạy agent làm thêm việc mới |
| | **Kết nối** | Công cụ ngoài (MCP), kênh chat (Telegram), API cho ứng dụng khác |
| | **Tính cách & trí nhớ** | Agent là ai, nhớ gì về bạn |
| **Hệ thống** | **Mô hình AI** | Chọn "bộ não" cho agent |
| | **Thống kê** | Agent đã làm gì và tốn bao nhiêu |
| | **Cài đặt** | Tính năng, an toàn, mật khẩu |

Ở đầu thanh bên có nút chuyển ngôn ngữ **Tiếng Việt / English**, và ở cuối có nút đổi giao diện sáng/tối. Rê chuột vào một mục để xem mô tả ngắn.

## 4. Trò chuyện với agent

Vào **Trò chuyện**, gõ yêu cầu và nhấn Enter (Shift+Enter để xuống dòng). Agent sẽ trả lời; khi cần, nó tự gọi công cụ (đọc file, tìm web, chạy lệnh…) và bạn thấy từng bước hiện ngay trong khung chat.

### Mỗi hội thoại có một thư mục làm việc riêng

Mọi file agent tạo ra (script, báo cáo, ảnh…) và file bạn đính kèm nằm trong thư mục riêng của hội thoại đó. Bấm biểu tượng panel ở góc phải trên để mở **panel Workspace**, gồm các tab:

- **Tệp**: xem, sửa, tải về, xóa file của hội thoại.
- **Terminal**: các lệnh agent đã chạy và kết quả.
- **Hoạt động**: dòng thời gian các công cụ đã gọi.

### Ô soạn tin

- **Dấu +**: đính kèm file hoặc ảnh. Bạn cũng có thể kéo thả file vào khung chat.
- **Microphone**: nhập bằng giọng nói (dùng nhận dạng giọng nói của trình duyệt).
- **Gõ `/`**: chọn một kỹ năng để dùng ngay.
- **Gõ `@`**: gọi một dịch vụ MCP (Notion, Linear…) hoặc MCP server cụ thể, xem [mục 9](#9-kết-nối-công-cụ-ngoài-telegram-api).
- **Chọn mô hình** (ví dụ "local · qwen2.5:3b"): đổi mô hình cho riêng hội thoại này.
- **Mức nỗ lực** ("Tự động", thấp, vừa, cao): bắt mô hình suy nghĩ kỹ hơn ở câu khó, nhưng chậm và tốn hơn.

### Quyền của agent (ô "Mặc định" ở góc dưới trái)

Đây là cài đặt quan trọng nhất về an toàn. Bạn đổi được ngay trong từng hội thoại:

| Chế độ | Ý nghĩa |
|---|---|
| **Mặc định** | Theo chính sách trong Cài đặt: ghi file trong thư mục của hội thoại thì được, chạy lệnh shell hoặc đụng file ngoài thư mục thì hỏi bạn |
| **Chỉ đọc** | Chỉ được đọc và tra cứu. Chặn ghi file, chạy lệnh, và các công cụ làm thay đổi dữ liệu |
| **Hỏi trước** | Hỏi bạn trước **mỗi** lần ghi file, chạy lệnh, gọi công cụ ngoài hoặc gửi yêu cầu HTTP làm thay đổi dữ liệu |
| **Toàn quyền** | Không hỏi gì cả. Chỉ dùng khi bạn tin tưởng hoàn toàn việc đang làm |

Khi agent cần xin phép, một thẻ **"Agent muốn chạy lệnh shell…"** hiện ra kèm đúng lệnh sẽ chạy. Bấm **Cho phép** hoặc **Từ chối**. Đọc kỹ lệnh trước khi cho phép.

### Các thao tác với tin nhắn

- **Sửa và gửi lại**: rê chuột vào tin nhắn cuối của bạn.
- **Tạo lại**: yêu cầu agent trả lời lại câu cuối.
- **Đọc to**: dưới mỗi câu trả lời có nút đọc bằng giọng nói của trình duyệt (không tốn phí, không gửi dữ liệu đi).
- **Tìm kiếm hội thoại**: ô tìm ở danh sách bên trái tìm cả nội dung các cuộc trò chuyện cũ.

### Kế hoạch cho việc nhiều bước

Với việc phức tạp, agent tự lập **kế hoạch** và hiện thành một thẻ "Kế hoạch" ngay trên ô soạn tin, tick dần từng bước khi làm xong. Bạn có thể nói rõ: "Hãy lập kế hoạch 4 bước rồi làm từng bước".

### Giao việc cho nhiều agent con

Agent có thể giao việc cho các **agent con chuyên trách** và gom kết quả lại. Ví dụ:

> Hãy giao song song cho 2 agent con: researcher tìm hiểu "Python 3.14 có gì mới", coder viết hàm tính số Fibonacci vào file fib.py. Rồi tổng hợp lại cho tôi.

Các vai trò có sẵn: **researcher** (tìm và tổng hợp thông tin web), **coder** (viết, chạy và sửa code), **reviewer** (chỉ đọc và phản biện). Bạn chỉnh được trong Cài đặt → Tính năng. File do agent con tạo ra nằm chung thư mục với hội thoại cha, nên bạn thấy ngay trong tab **Tệp**.

> Lưu ý: model nhỏ (như qwen2.5:3b) gọi nhiều công cụ song song kém ổn định. Với việc này, chọn một mô hình mạnh hơn như Gemini ở ô chọn mô hình.

### Ảnh trong hội thoại

- Agent có thể **tạo ảnh** từ mô tả (cần cấu hình nhà cung cấp tạo ảnh, xem [mục 11](#11-các-tính-năng-nâng-cao)), ảnh hiện ngay trong khung chat.
- Agent có thể **xem ảnh** bạn đính kèm. Nếu mô hình chính không xem được ảnh, nó dùng nhà cung cấp "xem ảnh" bạn chọn.

## 5. Giao việc dài: trang Tác vụ

Dùng khi việc mất nhiều phút và bạn không muốn ngồi canh: nghiên cứu, viết báo cáo, xử lý nhiều file.

1. Vào **Tác vụ**, gõ việc cần làm vào ô lớn (hoặc bấm một gợi ý), bấm **Giao việc** hoặc Ctrl+Enter.
2. Việc chạy ngầm. Bạn có thể đóng trang. Mục **Đang làm** có thanh tiến độ và số bước, kèm nút **Dừng**.
3. Xong, bạn nhận thông báo trong Hộp thư (và Telegram nếu đã nối). Bấm vào việc ở mục **Đã xong** để đọc kết quả, chép kết quả, hoặc xem agent đã làm thế nào.

Bấm dòng **"Mức tự do"** để chọn quyền cho việc này:

| Mức | Làm được gì |
|---|---|
| **Chỉ xem** | Chỉ đọc và tìm thông tin |
| **Làm việc an toàn** (mặc định) | Tạo file trong thư mục làm việc. Việc nguy hiểm tự bị từ chối |
| **Toàn quyền** | Chạy cả lệnh trên máy bạn. Chỉ chọn khi bạn tin việc này |

Việc nền không có ai ngồi duyệt, nên mọi thao tác cần xin phép bị từ chối nếu bạn không chọn Toàn quyền. Bạn cũng chọn được **vai trò** (researcher, coder, reviewer) để giao đúng người.

Nếu server khởi động lại giữa chừng, việc đang chạy được đánh dấu **"Bị gián đoạn"**; bạn giao lại là được.

## 6. Việc tự động theo lịch

Trang **Tự động hóa** cho agent làm việc vào giờ bạn chọn, rồi báo kết quả.

### Tạo việc mới

1. Bấm **Tạo việc mới**, hoặc bấm một **mẫu** (Tóm tắt tin buổi sáng, Nhắc việc cuối ngày, Báo cáo cuối tuần, 5 từ tiếng Anh mỗi ngày).
2. Đặt tên và mô tả agent cần làm mỗi lần chạy.
3. Chọn lịch: **Mỗi ngày**, **Các ngày trong tuần**, **Một ngày trong tuần**, **Mỗi giờ** hoặc **Cứ sau vài phút**, rồi chọn giờ. Dòng xem trước (ví dụ "Mỗi ngày lúc 08:00") cho bạn biết lịch đã đúng chưa. Người rành có thể chọn "Tùy chỉnh" để nhập biểu thức cron.
4. Tick **Báo kết quả cho tôi** để nhận kết quả trong Hộp thư và Telegram.

Mỗi thẻ việc cho bạn: bật/tắt bằng công tắc, **Chạy thử ngay**, Sửa, Xóa, và xem kết quả lần chạy trước.

> Việc chạy ngầm không có người duyệt, nên agent không chạy được lệnh shell trên máy bạn trong các việc này.

### Heartbeat: "Agent tự để mắt giúp bạn"

Bật công tắc này thì cứ mỗi N phút (mặc định 60) agent tự đọc danh sách trong file `HEARTBEAT.md` (sửa ở trang **Tính cách & trí nhớ**) và làm theo. Có gì đáng báo thì nó nhắn bạn, còn không thì im lặng. Ví dụ nội dung `HEARTBEAT.md`:

```
- Kiểm tra xem còn bao nhiêu dung lượng đĩa; báo tôi nếu dưới 10%.
- Nếu hôm nay là thứ Sáu, nhắc tôi nộp báo cáo tuần.
```

Xóa hết nội dung file để tạm dừng. Bấm **Tùy chọn** để đổi số phút hoặc mô hình, và **Kiểm tra thử ngay** để chạy thử.

## 7. Kỹ năng (Skills)

**Kỹ năng** là các bộ hướng dẫn dạy agent làm một việc cụ thể (ví dụ đọc PDF, tra thời tiết, quản lý lịch). Trang **Kỹ năng** có hai phần:

- **Đã cài**: danh sách kỹ năng bạn có. Bật/tắt từng cái, xem nội dung, điền khóa API nếu kỹ năng cần. Kỹ năng còn thiếu điều kiện (thiếu chương trình hoặc biến môi trường) hiển thị rõ cần gì.
- **Khám phá**: tìm và cài kỹ năng từ **ClawHub**, kho kỹ năng công khai. Có cảnh báo nếu một kỹ năng bị đánh dấu đáng ngờ.

Bạn cũng tự tạo kỹ năng bằng nút **Tạo kỹ năng**. Một kỹ năng là một thư mục trong `user-data/workspace/skills/<tên>/` có file `SKILL.md`. Dùng trong chat bằng cách gõ `/` rồi chọn tên.

> **Cẩn thận:** kỹ năng tải từ internet chỉ là hướng dẫn, nhưng có thể bảo agent chạy lệnh. Hãy đọc `SKILL.md` trước khi cài và giữ bật xác nhận chạy lệnh. Bạn cũng có thể cài nhanh từ dòng lệnh: `argus skills install <chủ>/<tên>`.

### Gợi ý tạo kỹ năng từ việc lặp lại

Khi bạn gửi cùng một kiểu yêu cầu ở **3 cuộc trò chuyện khác nhau**, Argus nhận ra và hiện thẻ "Tạo kỹ năng (hoặc tự động hóa) cho việc này nhé?" ở Trang chủ, kèm một thông báo. Bản nháp đã được soạn sẵn:

- Việc mang tính định kỳ ("mỗi sáng", "hằng tuần") được đề xuất thành **tự động hóa** (có sẵn lịch cron và lời nhắc).
- Các việc còn lại thành **kỹ năng** (tên, mô tả, các bước).

Bấm **Xem bản nháp**, chỉnh nếu muốn (kể cả đổi loại) rồi **Tạo**. Bấm dấu X để bỏ qua; việc đó sẽ không bị nhắc lại. Việc phát hiện chỉ so khớp từ khóa trên máy bạn, không tốn token; model chỉ được gọi một lần để soạn bản nháp. Tắt tại Cài đặt → Agent → "Gợi ý tạo kỹ năng từ việc lặp lại".

## 8. Mô hình AI

Trang **Mô hình AI** là nơi chọn "bộ não" cho agent.

- **Mô hình của bạn**: mỗi mô hình là một thẻ cho biết đang là mô hình chính hay không, đã có khóa API chưa. Bấm **Thử kết nối** để kiểm tra, **Chỉnh sửa** để nhập khóa API và chọn model, **Dùng làm chính** để đặt làm mô hình mặc định.
- **Thêm mô hình AI**: bấm một ô dịch vụ.
  - *Chạy trên máy bạn* (miễn phí, riêng tư): **Ollama**, **LM Studio**. Cần cài sẵn và tải model về máy.
  - *Dịch vụ đám mây* (cần khóa API lấy từ trang của họ): **Google Gemini**, **Claude**, **OpenAI**, **DeepSeek**, **OpenRouter**, **Groq**, và "Dịch vụ khác" cho mọi dịch vụ tương thích OpenAI. Mục "Xem thêm dịch vụ" còn có vLLM, Mistral, xAI, Cerebras, Together, Fireworks, Qwen.
- *Dùng CLI đã đăng nhập (không cần API key)*: dùng tài khoản đã đăng nhập sẵn trong một CLI trên máy bạn. Có ba CLI dựng sẵn: **Claude Code** (lệnh `claude`), **Antigravity** (lệnh `agy`, tài khoản Google) và **Codex** (lệnh `codex`, tài khoản ChatGPT/OpenAI); thêm **CLI khác** cho mọi chương trình nhận câu hỏi qua stdin và in câu trả lời ra stdout. Bạn cần cài CLI và chạy nó một lần trong terminal để đăng nhập. Đây là cách thứ hai để xác thực, bên cạnh API key: bạn chọn một trong hai bằng cách bấm ô tương ứng (ví dụ Claude dùng API key, hay Claude Code dùng CLI). Xem lưu ý bên dưới.
- **Mô hình dự phòng**: nếu mô hình chính lỗi hoặc quá tải, agent tự chuyển sang các mô hình bạn tick, theo thứ tự.

Sau khi đổi, nhớ bấm **Lưu thay đổi** ở góc phải trên.

Trong **Chỉnh sửa → Tùy chọn nâng cao** có: địa chỉ máy chủ (Base URL), lấy khóa từ biến môi trường, độ sáng tạo (temperature), giá token để ước tính chi phí, và công tắc **"Model hiểu được ảnh"** (chỉ bật nếu mô hình hỗ trợ).

**Về mô hình dùng CLI.** Argus chạy CLI ở chế độ không giao diện và tắt công cụ riêng của nó; Argus vẫn tự điều khiển công cụ nên phê duyệt, kế hoạch và trí nhớ hoạt động như thường. Đổi lại, mỗi bước mở một tiến trình CLI nên chậm hơn (khoảng 3 giây mỗi bước với Claude Code, 7–17 giây với Antigravity), không xem được ảnh và không có ô chọn "mức nỗ lực". Biến `ANTHROPIC_API_KEY` trong môi trường bị bỏ qua để CLI dùng đúng tài khoản đăng nhập. Antigravity và Codex có công cụ riêng (đọc/ghi file, chạy lệnh) mà không tắt được bằng cờ; Argus yêu cầu chúng chỉ trả lời bằng văn bản, và Codex được chạy ở chế độ sandbox chỉ đọc. Antigravity tạo một hội thoại trong lịch sử của `agy` mỗi lần gọi. Codex **chưa được kiểm chứng với bản thật** (chưa cài trên máy phát triển). **Hãy đọc điều khoản của hãng** về việc dùng gói thuê bao theo cách này (Anthropic từng cấm dùng token đăng nhập của gói thuê bao trong ứng dụng bên thứ ba; Argus không lấy token, chỉ chạy chính CLI chính thức, nhưng bạn nên tự xác nhận). Nếu không chắc, dùng API key.

**Chọn mô hình nào?** Mô hình nhỏ chạy trên máy (như qwen2.5:3b) miễn phí và riêng tư nhưng yếu, hay quên và gọi công cụ kém. Việc nhiều bước, giao việc cho agent con, hoặc điều khiển trình duyệt nên dùng mô hình đám mây mạnh hơn.

## 9. Kết nối: công cụ ngoài, Telegram, API

Trang **Kết nối** có ba tab (MCP server, Kênh chat, API & Token). Các dịch vụ bên ngoài nằm ở mục **Plugin** riêng trên thanh bên.

### MCP server và Plugin

MCP là cách "cắm thêm" công cụ cho agent. Có hai nơi:

**Kết nối → tab "MCP server"**: máy chủ chạy trên máy bạn hoặc tự khai báo (duyệt web bằng Playwright, đọc/ghi file, server MCP của bạn). Bấm **Thêm MCP server**, chọn một mẫu (**Duyệt web**, **Đọc/ghi file**) hoặc **Tự cấu hình**, đặt tên, bấm **Thử kết nối** để thấy các công cụ nó cung cấp, rồi **Lưu**. Công cụ mới tự xuất hiện cho agent, tên dạng `tênserver__têntool`.

**Mục "Plugin"** (thanh bên, nhóm Khả năng của agent): danh mục **54 dịch vụ đã kiểm chứng** chia theo lĩnh vực, kể cả những cái bạn chưa dùng: Lập trình và triển khai (GitHub, GitLab, Vercel, Netlify, Cloudflare, Sentry, Datadog, Context7, DeepWiki, Microsoft Learn…), Dữ liệu và hạ tầng (Neon, Supabase, PostHog, Apify, Hugging Face…), Tìm kiếm và tài liệu (Exa, Firecrawl, Tavily), Công việc và cộng tác (Notion, Linear, Asana, Atlassian, ClickUp, monday, Airtable, Todoist, Miro, Zapier…), Thiết kế và website (Canva, Webflow, Wix), Kinh doanh và thanh toán (Stripe, PayPal, Square, Intercom, Ramp, Clay, Close, Shopify, GoDaddy), cùng Buildkite, Better Stack, Grafana, Globalping, AWS Knowledge, AllTrails, Amplitude, Cloudinary. Gõ vào ô tìm kiếm để lọc. Muốn dùng dịch vụ nào, bấm **Dùng** ở dòng đó. Có ba kiểu, ghi rõ ở từng dòng:

- **Đăng nhập bằng tài khoản** (đa số): Argus thêm kết nối và mở trang đăng nhập của dịch vụ trong tab mới. Bạn bấm **Cho phép** (trong vòng 5 phút) rồi đóng tab; dòng dịch vụ chuyển sang **Đã kết nối** kèm số công cụ.
- **Không cần đăng nhập** (nhãn xanh): kết nối ngay.
- **Cần token** (nhãn xanh dương, ví dụ GitHub): dịch vụ không cho đăng nhập một chạm, nên hộp thoại hiện ra kèm đường dẫn tới trang tạo token. Dán token vào, Argus lưu (mã hóa) và gửi kèm header của nó.

Bấm vào dòng đã kết nối để xem công cụ và bật/tắt từng cái. **Đăng xuất** xóa token đã lưu; biểu tượng thùng rác **Gỡ** dịch vụ khỏi Argus.

**Tìm thêm trong thư viện MCP chính thức.** Khi bạn gõ từ khóa (ví dụ "stripe", "vercel"), bên dưới danh mục hiện thêm **kết quả từ thư viện MCP chính thức** (registry.modelcontextprotocol.io). Bấm **Dùng** thì Argus tự thăm dò xem server đó cần đăng nhập kiểu nào (OAuth, token hay không cần) rồi làm tương ứng. **Cẩn thận:** thư viện này do cộng đồng đăng và Argus không kiểm duyệt từng mục; mục có nhãn **Cộng đồng** chưa được xác minh thương hiệu. Argus hỏi xác nhận trước khi thêm, và công cụ của chúng vẫn phải qua bước xin phép. Chỉ dùng nguồn bạn tin.

Dịch vụ không có trong danh mục lẫn thư viện thì thêm ở mục **Dịch vụ do bạn thêm → Thêm dịch vụ khác** (nhập địa chỉ MCP từ xa).

Token đăng nhập được **mã hóa** trong cơ sở dữ liệu (cùng khóa chủ với API key) và không nằm trong `config.json`; Argus tự làm mới khi hết hạn. Nếu bạn đổi địa chỉ hoặc cổng của Argus thì phải đăng nhập lại. Một số dịch vụ không cho ứng dụng tự đăng ký hoặc cần cấu hình riêng (ví dụ Figma, Slack, HubSpot, Box, Gamma, Calendly), nên không có trong danh mục: tôi đã thử và chúng không dùng được theo cách một chạm.

**Gọi dịch vụ bằng dấu `@` trong Trò chuyện.** Gõ `@` ở ô soạn tin để chọn một dịch vụ hoặc MCP server (kèm logo và trạng thái), ví dụ "Tìm trang họp tuần trước trong @notion". Khi bạn gọi `@tên`, agent chỉ thấy công cụ của dịch vụ đó (đỡ tốn token, đỡ chọn nhầm) và được nhắc dùng đúng nó; gọi nhiều dịch vụ thì nêu từng `@tên`. Tên dịch vụ trong tin nhắn được tô màu. Nếu dịch vụ chưa kết nối, bạn thấy thông báo và agent hướng dẫn đăng nhập.

Công tắc **"Hỏi tôi trước khi dùng công cụ này"** nên để bật. Công cụ chỉ để xem thông tin luôn chạy thẳng.

### Kênh chat: Telegram

Để nhắn tin cho agent từ điện thoại:

1. Mở Telegram, nhắn cho **@BotFather**, gửi `/newbot` và làm theo hướng dẫn. Bạn nhận một **token** dạng `123456:ABC...`.
2. Trong **Kết nối → Kênh chat → Telegram**, dán token, bấm **Kiểm tra** (báo tên bot nếu đúng), rồi bật công tắc **Bật Telegram**.
3. Bấm **Tạo mã ghép đôi** trên giao diện, rồi nhắn cho bot trên Telegram: `/pair <mã>`.

Chỉ tài khoản đã ghép đôi mới dùng được bot, nên người lạ nhắn vào không điều khiển được agent của bạn. Các lệnh trong Telegram:

| Lệnh | Tác dụng |
|---|---|
| `/new` | Bắt đầu hội thoại mới |
| `/stop` | Hủy yêu cầu đang chờ phê duyệt |
| `/id` | Cho biết ID Telegram của bạn |
| `/help` | Hiện trợ giúp |

Khi agent cần xin phép (ví dụ chạy lệnh), bot hỏi lại ngay trên Telegram với nút Cho phép/Từ chối. Agent chạy trên máy bạn và nhận tin bằng long polling, nên **không cần mở cổng ra internet**.

> Giữ **token bot** bí mật. Nếu lỡ lộ, vào @BotFather gửi `/revoke` để lấy token mới.

### API và Token

Cho phép ứng dụng khác (script của bạn, Claude Code, Cursor…) giao việc cho agent. Tạo một **token** ở tab này (tên dạng `agt_...`, chỉ hiện đầy đủ một lần), rồi gọi:

```bash
curl -s http://127.0.0.1:8787/v1/run \
  -H "Authorization: Bearer agt_xxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Tóm tắt file notes.md", "timeout": 120}'
```

Mặc định API từ chối chạy lệnh shell. Muốn cho phép, tạo token với tùy chọn **cho phép chạy lệnh** và truyền `exec_policy` (`deny`, `allow` hoặc `allowlist`). Xem thêm trong [kien-truc.md](kien-truc.md#8-api-bên-ngoài).

## 10. Tính cách và trí nhớ

Trang **Tính cách & trí nhớ** là nơi bạn sửa bốn file định hình agent:

| File | Nội dung |
|---|---|
| **SOUL** | Tính cách, giọng điệu, quy tắc làm việc. Luôn nằm trong lời nhắc của agent |
| **USER** | Thông tin về bạn (tên, sở thích, công việc) để agent cá nhân hóa câu trả lời |
| **HEARTBEAT** | Danh sách việc agent tự kiểm tra mỗi lần heartbeat |
| **MEMORY** | Bộ nhớ dài hạn. Agent tự ghi vào đây khi bạn nói "hãy nhớ…". Bạn có thể sửa hoặc xóa |

Tab **MEMORY** có nút **Dọn bằng AI**: AI gộp mục trùng, bỏ thông tin lỗi thời và sắp xếp lại. Bạn xem đề xuất (những gì sẽ bỏ, sẽ thêm hoặc viết lại) rồi mới bấm **Áp dụng**; bản cũ luôn được lưu thành `MEMORY.md.bak-<giờ>` để hoàn tác. Chưa có gì bị ghi cho tới khi bạn bấm Áp dụng.

Ngoài MEMORY.md, agent còn **tìm lại các hội thoại cũ** khi cần nhớ điều bạn từng nói (công cụ `memory_search`), kết hợp tìm theo từ khóa và tìm theo ý nghĩa (xem [mục 11](#11-các-tính-năng-nâng-cao)).

## 11. Các tính năng nâng cao

Vào **Cài đặt → tab Tính năng**.

### Trình duyệt

Agent tự mở trang web, bấm, điền form và chụp màn hình bằng Chromium trên máy bạn. Cần cài Chromium hoặc Chrome (`argus doctor` báo nếu thiếu).

- **Chạy ẩn**: tắt đi để xem agent thao tác trực tiếp.
- **Cho phép địa chỉ nội bộ**: mặc định tắt, chặn `localhost` và mạng LAN để một trang web độc hại không dò được mạng nhà bạn.
- **Tự đóng sau N phút không dùng**.

Ví dụ: "Mở trang vnexpress.net và cho tôi 5 tiêu đề đầu."

### Trí nhớ theo nghĩa

Tìm lại hội thoại và ghi chú cũ theo **ý nghĩa**, không chỉ theo từ khóa.

- **Tự chọn** (mặc định): dùng Ollama nếu có model embedding, nếu không dùng chế độ **hash**, tức khớp theo từ gần giống (không phân biệt dấu, chịu lỗi gõ), **chưa hiểu nghĩa thật**.
- Muốn hiểu nghĩa thật: chọn **API tương thích OpenAI**, chọn nhà cung cấp Gemini hoặc OpenAI, và đặt model embedding (ví dụ `gemini-embedding-001`, `text-embedding-3-small`).
- Sau khi đổi model embedding, bấm **Lập lại chỉ mục**.
- Với API có phí, mỗi tin nhắn mới được nhúng ngầm và tốn một lượng rất nhỏ. Tắt bằng công tắc **Tự lập chỉ mục**.

### Ảnh

- **Provider tạo ảnh** và **model tạo ảnh** (mặc định `gemini-2.5-flash-image`). Có thể tốn phí theo từng ảnh.
- **Provider để xem ảnh**: dùng khi mô hình chính không xem được ảnh.

### Điều khiển máy tính (thử nghiệm)

Agent xem màn hình và điều khiển chuột, bàn phím. **Mặc định tắt** và mỗi thao tác đều hỏi bạn.

> **Cẩn thận:** agent có thể bấm vào bất cứ thứ gì trên màn hình, kể cả cửa sổ đang hiện mật khẩu. Chỉ bật khi bạn ngồi canh, và đừng để ở chế độ Toàn quyền khi vắng mặt. Trên Linux cần `xdotool` (X11) hoặc `ydotool` + `wtype` (Wayland); trên macOS nên cài `cliclick` và cấp quyền Accessibility, Screen Recording.

### Agent con và việc dài

Chỉnh độ sâu tối đa (agent con có được tạo agent con khác không), số việc chạy song song, số bước tối đa, và vai trò (nhà cung cấp, số bước, danh sách công cụ cho phép) trong mục "Vai trò của agent con".

### Các tab khác của Cài đặt

- **Cơ bản**: có hỏi xác nhận trước khi chạy lệnh shell không (khuyên bật). **Tùy chọn nâng cao** có số bước tối đa mỗi lượt, số tin nhắn gửi kèm, thư mục workspace, ngưỡng tóm tắt hội thoại.
- **Công cụ**: bật/tắt từng công cụ. Tắt công cụ nào thì agent không thấy và không gọi được. Ít công cụ giúp mô hình nhỏ chọn đúng hơn.
- **An toàn**: chạy lệnh trong **Docker** cách ly; **mật khẩu giao diện**; tình trạng **mã hóa khóa bí mật**.
- **Nâng cao**: địa chỉ ClawHub.

## 12. Thống kê và lịch sử

Trang **Thống kê** có hai tab:

- **Thống kê & chi phí**: số tin nhắn, số token đã dùng, số lần gọi công cụ, độ trễ trung bình, biểu đồ theo ngày (7/30/90 ngày), bảng theo từng mô hình và các công cụ dùng nhiều nhất. Chi phí chỉ là ước tính theo giá bạn nhập ở trang Mô hình AI.
- **Lịch sử thao tác**: nhật ký mọi công cụ agent đã gọi, nguồn gọi (chat, API, Telegram, tự động…), có cho phép hay từ chối, và kết quả. Có bộ lọc để tra cứu khi cần kiểm tra agent đã làm gì.

## 13. An toàn và quyền riêng tư

- **Chỉ nhận kết nối từ chính máy bạn.** Máy chủ nghe ở `127.0.0.1`, và từ chối các yêu cầu có tên máy chủ lạ (chống tấn công DNS rebinding).
- **Đặt mật khẩu nếu mở cho mạng LAN.** Vào **Cài đặt → An toàn → Bảo mật giao diện**. Nếu bạn cho phép truy cập từ máy khác (`argus start --host 0.0.0.0`), hãy luôn đặt mật khẩu và dùng HTTPS.
- **Khóa bí mật được mã hóa.** Khóa API, token Telegram và biến môi trường của MCP được mã hóa trong `user-data/config.json` bằng khóa chủ `user-data/data/master.key`. Điều này bảo vệ khi file config lộ riêng lẻ (gửi kèm báo lỗi, đẩy nhầm lên git); **không** bảo vệ khi kẻ tấn công có cả hai file hoặc đang chạy trên máy của bạn. Hãy sao lưu khóa chủ (xem mục 14).
- **Lệnh nguy hiểm luôn hỏi.** Chạy lệnh shell, đọc/ghi ngoài thư mục làm việc, gọi công cụ ngoài, gửi yêu cầu HTTP thay đổi dữ liệu. Chỉ chế độ Toàn quyền bỏ qua việc hỏi.
- **Sandbox Docker (tùy chọn).** Cài đặt → An toàn: chạy lệnh shell của agent trong container cách ly, mặc định không có mạng, chỉ thấy thư mục làm việc của hội thoại. Khuyên dùng khi cài kỹ năng từ internet.
- **Kỹ năng và MCP stdio chạy với quyền của bạn.** Chỉ cài thứ bạn tin tưởng.
- **Các việc bạn chưa duyệt không tự chạy.** Việc chạy ngầm và API mặc định từ chối mọi thao tác cần xin phép.

## 14. Sao lưu và khôi phục

Toàn bộ dữ liệu cá nhân nằm trong `user-data/`. Sao lưu định kỳ:

```bash
argus backup                                   # file nằm ở user-data/backups/
argus backup --encrypt                         # mã hóa bằng mật khẩu bạn nhập
argus backup --include-key --encrypt           # kèm khóa chủ, để khôi phục trên máy khác
argus backup --no-sessions                     # bỏ file của từng hội thoại cho nhẹ
```

Khôi phục:

```bash
argus restore <file-sao-lưu> --force
```

`--force` sao lưu dữ liệu hiện tại trước khi ghi đè. Nếu bản sao lưu không kèm khóa chủ, truyền `--master-key-file <đường-dẫn>`; thiếu khóa chủ thì các khóa API đã mã hóa không đọc lại được. Chi tiết xem [cli.md](cli.md#backup).

## 15. Xử lý sự cố

Bước đầu tiên luôn là chạy:

```bash
argus doctor
```

Nó kiểm tra Python, gói cài đặt, giao diện đã build chưa, quyền file, khóa bí mật, cơ sở dữ liệu, server, các mô hình, Docker, Telegram, trình duyệt, trí nhớ ngữ nghĩa… và gợi ý cách sửa. Thêm `--fix` để tự sửa những lỗi an toàn.

| Hiện tượng | Nguyên nhân thường gặp và cách xử lý |
|---|---|
| Trang trắng sau khi cập nhật | Server còn chạy bản cũ. Chạy `argus restart`, rồi tải lại trang bằng Ctrl+Shift+R |
| "Cần khóa API" ở thẻ mô hình | Mở **Chỉnh sửa**, dán khóa, bấm **Lưu thay đổi** |
| Lỗi 503 hoặc "high demand" từ Gemini | Dịch vụ đang quá tải. Thử lại sau, hoặc đặt một mô hình **dự phòng** |
| Agent trả lời kỳ lạ, quên ngữ cảnh | Mô hình nhỏ có context ngắn. Giảm "Số tin nhắn gửi kèm" hoặc dùng mô hình mạnh hơn |
| Agent không tạo được file trong việc nền | Việc nền cần mức "Làm việc an toàn" trở lên. Mức "Chỉ xem" không cho ghi |
| Bot Telegram im lặng | Server chưa chạy, hoặc chưa bật Telegram trong Kết nối. Bot báo "chưa được phép" thì làm bước ghép đôi `/pair <mã>` |
| Không tìm thấy bot Telegram | Mở thẳng link `t.me/<tên_bot>` thay vì gõ tên vào ô tìm kiếm |
| Trình duyệt không chạy | Chưa cài Chromium/Chrome. `argus doctor` báo cách cài |
| Thấy "Chế độ hash" ở trí nhớ ngữ nghĩa | Bình thường. Muốn hiểu nghĩa thật, chọn embedding OpenAI/Gemini như mục 11 |
| Quên mật khẩu giao diện | Sửa `user-data/config.json`: xóa giá trị `password_hash` trong mục `auth`, rồi `argus restart` |
| Mất khóa chủ | Các khóa API không giải mã được. Nhập lại khóa ở trang Mô hình AI. Lần sau hãy sao lưu kèm `--include-key --encrypt` |

Xem log của server: `argus logs -f`.
