import { Languages } from 'lucide-react'
import { cn } from '@/lib/utils'
import { setLang, t, tk, useLang, type Lang } from '@/lib/i18n.ts'

const OPTIONS: { id: Lang; short: string; label: string }[] = [
  { id: 'vi', short: 'VI', label: tk('Tiếng Việt') }, // ten ngon ngu luon viet bang chinh ngon ngu do
  { id: 'en', short: 'EN', label: 'English' },
]

/** Chon ngon ngu giao dien. Thanh ben rong: hai nut VI | EN; thanh ben hep: mot nut doi qua lai. */
export function LangSwitcher() {
  const lang = useLang()
  const next = OPTIONS.find((o) => o.id !== lang)!
  return (
    <>
      <div role="group" aria-label={t('Ngôn ngữ')} className="hidden items-center gap-1 rounded-lg bg-bg p-0.5 md:flex">
        <Languages className="ml-1.5 size-3.5 shrink-0 text-muted" aria-hidden />
        {OPTIONS.map((o) => (
          <button key={o.id} onClick={() => setLang(o.id)} aria-pressed={lang === o.id} title={o.label} lang={o.id}
            className={cn('flex-1 rounded-md px-2 py-1 text-xs font-semibold transition', lang === o.id ? 'bg-panel2 text-fg shadow-sm' : 'text-muted hover:text-fg')}>
            {o.label}
          </button>
        ))}
      </div>
      <button onClick={() => setLang(next.id)} title={`${next.label}`} aria-label={`Switch to ${next.label}`} className="grid size-8 place-items-center rounded-lg text-xs font-bold text-muted transition hover:bg-panel2 hover:text-fg md:hidden">
        {lang.toUpperCase()}
      </button>
    </>
  )
}
