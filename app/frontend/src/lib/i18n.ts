/**
 * i18n gon nhe: khoa la chinh cau tieng Viet (ngon ngu goc), ban tieng Anh tra trong src/i18n/en/*.ts.
 *   t('Xin chào {name}', { name })     -> doi ngon ngu va noi bien
 *   tk('Hộp thư')                      -> chi danh dau khoa cho hang so cap module, dich luc render bang t(...)
 * Khoa chua dau tieng Viet ma thieu ban dich se bi script `npm run i18n:check` bao loi.
 * So nhieu: gia tri tieng Anh dang 'mot||{n} cai' (dang so it||dang so nhieu), chon theo vars.n === 1.
 */
import { useSyncExternalStore } from 'react'
import { EN } from '@/i18n/en/index.ts'

export type Lang = 'vi' | 'en'
const STORAGE_KEY = 'lang'

function detect(): Lang {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved === 'vi' || saved === 'en') return saved
  } catch { /* che do rieng tu: khong co localStorage */ }
  return typeof navigator !== 'undefined' && navigator.language?.toLowerCase().startsWith('vi') ? 'vi' : 'en'
}

let lang: Lang = detect()
const listeners = new Set<() => void>()
if (typeof document !== 'undefined') document.documentElement.lang = lang

export const getLang = () => lang
export const locale = () => (lang === 'vi' ? 'vi-VN' : 'en-US')

export function setLang(next: Lang) {
  if (next === lang) return
  lang = next
  try { localStorage.setItem(STORAGE_KEY, next) } catch { /* bo qua */ }
  document.documentElement.lang = next
  listeners.forEach((fn) => fn())
}

export function useLang(): Lang {
  return useSyncExternalStore((fn) => { listeners.add(fn); return () => { listeners.delete(fn) } }, getLang)
}

/** Danh dau chuoi can dich nhung chua dich ngay (dung cho hang so cap module). */
export const tk = (key: string) => key

export function t(key: string, vars?: Record<string, string | number>): string {
  let s = lang === 'en' ? (EN[key] ?? key) : key
  if (s.includes('||')) {
    const [one, many] = s.split('||')
    s = vars?.n === 1 ? one : many
  }
  return vars ? s.replace(/\{(\w+)\}/g, (_, k: string) => String(vars[k] ?? '')) : s
}
