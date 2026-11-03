/** Thong bao loi co tham so do server tra ve (tieng Viet). Chi dung khi giao dien dang o tieng Anh. */
export const SERVER_PATTERNS: [RegExp, string][] = [
  [/^provider '(.+)' không tồn tại$/, "Provider '$1' does not exist"],
  [/^tên MCP server chỉ gồm a-z, 0-9, - và _: (.+)$/, 'MCP server names may only contain a-z, 0-9, - and _: $1'],
  [/^không kết nối được ClawHub: (.+)$/, 'Could not connect to ClawHub: $1'],
  [/^không tải được: (.+)$/, 'Download failed: $1'],
  [/^biểu thức cron không hợp lệ: (.+)$/, 'Invalid cron expression: $1'],
  [/^đường dẫn nguy hiểm trong zip: (.+)$/, 'Unsafe path in zip: $1'],
  [/^đã có skill '(.+)' \(không cùng tác giả\)\. Xóa nó trước khi cài\.$/, "A skill named '$1' already exists (different author). Delete it before installing."],
  [/^không có skill '(.+)'$/, "No skill named '$1'"],
  [/^quá (\d+)s không kết nối được$/, 'Could not connect within $1s'],
  [/^agent trả về HTTP (\d+): (.+)$/, 'Agent returned HTTP $1: $2'],
]
