import { tk } from '@/lib/i18n.ts'

/** Lệnh `/` dựng sẵn (nội dung đầy đủ nằm ở backend: services/commands.py). needsArg: cần gõ thêm đối tượng; code: chỉ hiện khi đang ở chế độ Lập trình. */
export const SLASH_COMMANDS: { name: string; desc: string; needsArg: boolean; code: boolean }[] = [
  { name: 'review', desc: tk('Review thay đổi chưa commit: tìm bug, lỗi bảo mật (chỉ đọc)'), needsArg: false, code: true },
  { name: 'test', desc: tk('Chạy test của dự án và tự sửa nếu rớt'), needsArg: false, code: true },
  { name: 'commit', desc: tk('Commit đúng các file đã sửa, không push'), needsArg: false, code: true },
  { name: 'plan', desc: tk('Lập kế hoạch chi tiết cho một việc, chưa sửa gì'), needsArg: true, code: false },
  { name: 'explain', desc: tk('Giải thích một đoạn code hoặc cả dự án (chỉ đọc)'), needsArg: true, code: false },
]
