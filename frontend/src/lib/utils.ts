import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import { SERVER_PATTERNS } from '@/i18n/serverErrors.ts'
import { getLang, locale, t } from './i18n.ts'

/** Gop class, class sau thang class truoc khi xung dot (vd. w-full vs w-48). */
export const cn = (...v: ClassValue[]) => twMerge(clsx(v))

export const fmtNum = (n: number) => (n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${(n / 1e3).toFixed(1)}k` : String(n))

export function timeAgo(ts: number | null | undefined): string {
  if (!ts) return '—'
  const ms = ts < 1e12 ? ts * 1000 : ts // backend: giay; ClawHub: mili giay
  const s = Math.max(0, (Date.now() - ms) / 1000)
  if (s < 60) return t('vừa xong')
  if (s < 3600) return t('{n} phút trước', { n: Math.floor(s / 60) })
  if (s < 86400) return t('{n} giờ trước', { n: Math.floor(s / 3600) })
  return t('{n} ngày trước', { n: Math.floor(s / 86400) })
}

export function fmtDateTime(ts: number | null | undefined): string {
  if (!ts) return '—'
  return new Date(ts * 1000).toLocaleString(locale(), { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' })
}

/** Thong bao loi cho nguoi dung; loi tu server (tieng Viet) duoc dich neu co trong tu dien. */
export function errMsg(e: unknown): string {
  const msg = e instanceof Error ? e.message : String(e)
  if (getLang() === 'en') {
    const hit = SERVER_PATTERNS.find(([re]) => re.test(msg))
    if (hit) return msg.replace(hit[0], hit[1])
  }
  return t(msg)
}
