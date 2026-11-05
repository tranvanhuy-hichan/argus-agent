"""Lenh `/` dung san (review, test, commit, plan, explain). Tin nhan luu nguyen dang nguoi dung go ("/review"); model nhan ban mo rong."""
import re

COMMANDS: dict[str, str] = {
    "review": ("Review các thay đổi chưa commit trong dự án: chạy `git diff HEAD` (và đọc các file mới chưa được theo dõi), tìm bug, lỗi logic, thiếu xử lý lỗi, "
               "vấn đề bảo mật và hiệu năng. Trả lời theo mức độ nghiêm trọng; mỗi mục nêu file:dòng và cách sửa cụ thể; nếu ổn thì nói rõ. "
               "Chỉ đọc, KHÔNG sửa file nào."),
    "test": ("Tìm cách chạy test của dự án (package.json, pyproject, Makefile, CI...), chạy chúng và báo kết quả. Nếu có test rớt: đọc lỗi, tìm nguyên nhân gốc và sửa code "
             "(không sửa test cho qua), rồi chạy lại cho đến khi qua hoặc nói rõ vì sao chưa được."),
    "commit": ("Người dùng yêu cầu rõ ràng bạn commit. Xem `git status` và `git diff`, chỉ `git add` đúng các file liên quan (không dùng `git add -A`), "
               "viết message theo Conventional Commits, cùng phong cách với `git log -5 --oneline`. Nếu đang ở main/master thì tạo nhánh mới trước. KHÔNG push."),
    "plan": ("Lập kế hoạch chi tiết (dùng plan_set) cho yêu cầu sau. Đọc code liên quan trước (chỉ đọc), nêu các bước, file sẽ đổi và rủi ro. "
             "CHƯA sửa gì cho đến khi người dùng đồng ý."),
    "explain": ("Giải thích cho người dùng, dễ hiểu: nó làm gì, luồng chạy chính, các file quan trọng (kèm đường dẫn:dòng). Đọc code liên quan trước. Chỉ đọc, không sửa. "
                "Không nêu đối tượng cụ thể thì giải thích tổng quan dự án."),
}
_RE = re.compile(r"^/([a-z]+)(?:\s+(.*))?$", re.S)


def expand(text: str) -> str | None:
    """'/plan thêm đăng nhập' -> lời nhắc đầy đủ; không phải lệnh dựng sẵn thì trả None."""
    m = _RE.match(text.strip())
    if not m or m.group(1) not in COMMANDS:
        return None
    arg = (m.group(2) or "").strip()
    return COMMANDS[m.group(1)] + (f"\n\nYêu cầu của người dùng: {arg}" if arg else "")
