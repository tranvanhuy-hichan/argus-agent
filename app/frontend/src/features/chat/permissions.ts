import { ShieldAlert, ShieldCheck, ShieldEllipsis, ShieldQuestion, type LucideIcon } from 'lucide-react'
import { tk } from '@/lib/i18n.ts'

export type Permission = 'default' | 'readonly' | 'guarded' | 'full'
export type Effort = 'auto' | 'low' | 'medium' | 'high'

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
]
