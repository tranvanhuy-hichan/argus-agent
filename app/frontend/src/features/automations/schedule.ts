import { t, tk } from '@/lib/i18n.ts'

export type Freq = 'minutes' | 'hourly' | 'daily' | 'weekdays' | 'weekly' | 'custom'
export interface Sched { freq: Freq; every: number; time: string; dow: number; cron: string }

export const DAYS = [tk('Chủ nhật'), tk('Thứ Hai'), tk('Thứ Ba'), tk('Thứ Tư'), tk('Thứ Năm'), tk('Thứ Sáu'), tk('Thứ Bảy')]
const pad = (n: number) => String(n).padStart(2, '0')

/** Dung lich de chon -> bieu thuc cron. */
export function build(s: Sched): string {
  const [h, m] = s.time.split(':').map((x) => Number(x) || 0)
  switch (s.freq) {
    case 'minutes': return `*/${s.every} * * * *`
    case 'hourly': return '0 * * * *'
    case 'daily': return `${m} ${h} * * *`
    case 'weekdays': return `${m} ${h} * * 1-5`
    case 'weekly': return `${m} ${h} * * ${s.dow}`
    default: return s.cron
  }
}

/** Bieu thuc cron -> lich de chon (neu khong khop mau don gian thi la 'custom'). */
export function parse(cron: string): Sched {
  const base: Sched = { freq: 'custom', every: 15, time: '08:00', dow: 1, cron }
  const f = cron.trim().split(/\s+/)
  if (f.length !== 5) return base
  const [m, h, dom, mon, dow] = f
  if (dom !== '*' || mon !== '*') return base
  const step = /^\*\/(\d+)$/.exec(m)
  if (step && h === '*' && dow === '*') return { ...base, freq: 'minutes', every: Number(step[1]) }
  if (m === '0' && h === '*' && dow === '*') return { ...base, freq: 'hourly' }
  if (/^\d+$/.test(m) && /^\d+$/.test(h)) {
    const time = `${pad(Number(h))}:${pad(Number(m))}`
    if (dow === '*') return { ...base, freq: 'daily', time }
    if (dow === '1-5') return { ...base, freq: 'weekdays', time }
    if (/^[0-6]$/.test(dow)) return { ...base, freq: 'weekly', time, dow: Number(dow) }
  }
  return base
}

/** Mo ta bang loi: "Moi ngay luc 08:00". */
export function describe(cron: string): string {
  const s = parse(cron)
  switch (s.freq) {
    case 'minutes': return t('Mỗi {n} phút', { n: s.every })
    case 'hourly': return t('Mỗi giờ')
    case 'daily': return t('Mỗi ngày lúc {time}', { time: s.time })
    case 'weekdays': return t('Các ngày trong tuần lúc {time}', { time: s.time })
    case 'weekly': return t('{day} hàng tuần lúc {time}', { day: t(DAYS[s.dow]), time: s.time })
    default: return cron
  }
}
