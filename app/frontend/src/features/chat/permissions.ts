import { ShieldAlert, ShieldCheck, ShieldEllipsis, ShieldQuestion, type LucideIcon } from 'lucide-react'
import { tk } from '@/lib/i18n.ts'

export type Permission = 'default' | 'readonly' | 'guarded' | 'full'
export type Effort = 'auto' | 'low' | 'medium' | 'high' | 'thinking'

export const PERMISSIONS: { id: Permission; label: string; desc: string; icon: LucideIcon; tone: string }[] = [
  { id: 'default', label: tk('Mặc định'), desc: tk('Theo chính sách đã cấu hình trong Cài đặt.'), icon: ShieldCheck, tone: 'text-muted' },
  { id: 'readonly', label: tk('Chỉ đọc'), desc: tk('Chỉ đọc file trong phiên; chặn ghi file, lệnh shell và tool thay đổi dữ liệu.'), icon: ShieldEllipsis, tone: 'text-info' },
  { id: 'guarded', label: tk('Hỏi trước'), desc: tk('Hỏi bạn trước mỗi lần ghi file, chạy lệnh, gọi tool MCP hay gửi yêu cầu HTTP thay đổi dữ liệu.'), icon: ShieldQuestion, tone: 'text-warn' },
  { id: 'full', label: tk('Toàn quyền'), desc: tk('Không hỏi xác nhận; file và lệnh không bị giới hạn (trừ sandbox Docker nếu bật).'), icon: ShieldAlert, tone: 'text-bad' },
]

export const EFFORTS: { id: Effort; label: string }[] = [
  { id: 'auto', label: tk('Tự động') },
  { id: 'low', label: tk('Thấp') },
  { id: 'medium', label: tk('Vừa') },
  { id: 'high', label: tk('Cao') },
  { id: 'thinking', label: tk('Suy nghĩ (Thinking)') },
]

/** Quyền đã chọn được nhớ theo từng phiên (không bị đặt lại khi đổi phiên/đổi trang). '__new' là lựa chọn cho hội thoại chưa có id. */
const KEY = 'argus-perm:'
const VALID = new Set<string>(['default', 'readonly', 'guarded', 'full'])
export const permStore = {
  get(sid: string | null): Permission | null {
    try { const v = localStorage.getItem(KEY + (sid ?? '__new')); return v && VALID.has(v) ? (v as Permission) : null } catch { return null }
  },
  set(sid: string | null, p: Permission) { try { localStorage.setItem(KEY + (sid ?? '__new'), p) } catch { /* che do rieng tu */ } },
  clear(sid: string | null) { try { localStorage.removeItem(KEY + (sid ?? '__new')) } catch { /* */ } },
}
