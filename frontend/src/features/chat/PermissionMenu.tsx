import { useEffect, useRef, useState } from 'react'
import { Check } from 'lucide-react'
import { t } from '@/lib/i18n.ts'
import { cn } from '@/lib/utils'
import { PERMISSIONS, type Permission } from './permissions'

/** Nut chon quyen cua hoi thoai (kieu "Default / Read only / Guarded / Full access"), bam so 1-4 de chon nhanh khi dang mo. */
export function PermissionMenu({ value, onChange }: { value: Permission; onChange: (p: Permission) => void }) {
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  const current = PERMISSIONS.find((p) => p.id === value) ?? PERMISSIONS[0]

  const choose = (id: Permission) => {
    if (id === 'full' && !confirm(t('Toàn quyền: agent sẽ chạy lệnh và đọc/ghi file mà không hỏi bạn. Chỉ bật khi bạn tin tưởng yêu cầu của mình. Tiếp tục?'))) return
    onChange(id)
    setOpen(false)
  }

  useEffect(() => {
    if (!open) return
    const down = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false) }
    const key = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
      const n = Number(e.key)
      if (n >= 1 && n <= PERMISSIONS.length) { e.preventDefault(); choose(PERMISSIONS[n - 1].id) }
    }
    document.addEventListener('mousedown', down)
    document.addEventListener('keydown', key)
    return () => { document.removeEventListener('mousedown', down); document.removeEventListener('keydown', key) }
  })

  return (
    <div ref={box} className="relative">
      <button onClick={() => setOpen(!open)} aria-haspopup="menu" aria-expanded={open} title={t('Quyền')}
        className={cn('flex h-8 items-center gap-1.5 rounded-full px-3 text-sm transition hover:bg-panel2', current.tone, value !== 'default' && 'bg-panel2')}>
        <current.icon className="size-4" />{t(current.label)}
      </button>
      {open && (
        <div role="menu" aria-label={t('Quyền')} className="fade-in absolute bottom-full left-0 z-30 mb-2 w-[min(22rem,90vw)] rounded-xl border border-line bg-panel p-1.5 shadow-2xl">
          <p className="px-2.5 pb-1.5 pt-1 text-[11px] font-semibold uppercase tracking-wide text-muted">{t('Quyền')}</p>
          {PERMISSIONS.map((p, i) => (
            <button key={p.id} role="menuitemradio" aria-checked={p.id === value} onClick={() => choose(p.id)}
              className={cn('flex w-full items-start gap-3 rounded-lg px-2.5 py-2 text-left transition hover:bg-panel2', p.id === value && 'bg-panel2')}>
              <p.icon className={cn('mt-0.5 size-4 shrink-0', p.tone)} />
              <span className="min-w-0 flex-1"><span className="block text-sm font-medium">{t(p.label)}</span><span className="block text-xs text-muted">{t(p.desc)}</span></span>
              {p.id === value ? <Check className="mt-0.5 size-4 shrink-0 text-accent" /> : <span className="mt-0.5 text-xs tabular-nums text-muted/70">{i + 1}</span>}
            </button>
          ))}
          <p className="px-2.5 pb-1 pt-1.5 text-[11px] text-muted">{t('Chỉ áp dụng cho hội thoại hiện tại.')}</p>
        </div>
      )}
    </div>
  )
}
