import { useEffect, useRef, useState } from 'react'
import { Check, SlidersHorizontal } from 'lucide-react'
import { t } from '@/lib/i18n.ts'
import { cn } from '@/lib/utils'
import { EFFORTS, PERMISSIONS, type Effort, type Permission } from './permissions'
import type { ProviderOption } from './Composer'

/** Một nút gom mọi tuỳ chọn của hội thoại: model, mức suy luận và quyền. */
export function SettingsMenu({ providers, provider, onProvider, effort, onEffort, effortOff, permission, onPermission }: {
  providers: ProviderOption[]; provider: string; onProvider: (id: string) => void
  effort: Effort; onEffort: (e: Effort) => void; effortOff: boolean
  permission: Permission; onPermission: (p: Permission) => void
}) {
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  const perm = PERMISSIONS.find((x) => x.id === permission) ?? PERMISSIONS[0]
  const cur = providers.find((x) => x.id === provider)

  useEffect(() => {
    if (!open) return
    const down = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false) }
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', down)
    document.addEventListener('keydown', key)
    return () => { document.removeEventListener('mousedown', down); document.removeEventListener('keydown', key) }
  }, [open])

  const choosePerm = (id: Permission) => {
    if (id === 'full' && !confirm(t('Toàn quyền: agent sẽ chạy lệnh và đọc/ghi file mà không hỏi bạn. Chỉ bật khi bạn tin tưởng yêu cầu của mình. Tiếp tục?'))) return
    onPermission(id)
  }
  const summary = `${provider}${cur ? ` · ${cur.model}` : ''} · ${t(perm.label)}`

  return (
    <div ref={box} className="relative">
      <button onClick={() => setOpen(!open)} aria-haspopup="dialog" aria-expanded={open} title={summary} aria-label={t('Tuỳ chọn hội thoại')}
        className={cn('flex h-8 max-w-44 items-center gap-1.5 rounded-full px-3 text-sm transition hover:bg-panel2', open || permission !== 'default' ? 'bg-panel2' : '', permission !== 'default' ? perm.tone : 'text-muted hover:text-fg')}>
        <SlidersHorizontal className="size-4 shrink-0" /><span className="truncate">{provider}</span>
        {permission !== 'default' && <span className="size-1.5 shrink-0 rounded-full bg-current" aria-hidden />}
      </button>
      {open && (
        <div role="dialog" aria-label={t('Tuỳ chọn hội thoại')} className="fade-in absolute bottom-full right-0 z-30 mb-2 w-[min(22rem,90vw)] space-y-4 rounded-xl border border-line bg-panel p-3 shadow-2xl">
          <section>
            <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted">{t('Mô hình AI')}</p>
            <select value={provider} onChange={(e) => onProvider(e.target.value)} aria-label={t('Chọn provider')} className="h-9 w-full cursor-pointer rounded-lg border border-fg/20 bg-bg px-2.5 text-sm focus:border-accent focus:outline-none">
              {providers.map((x) => <option key={x.id} value={x.id}>{x.id} · {x.model}</option>)}
            </select>
          </section>
          <section>
            <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted">{t('Mức suy luận')}</p>
            <div className="grid grid-cols-4 gap-1 rounded-lg bg-bg p-1" role="radiogroup" aria-label={t('Mức suy luận')} title={effortOff ? t('Chưa hỗ trợ với provider Anthropic') : undefined}>
              {EFFORTS.map((e) => (
                <button key={e.id} role="radio" aria-checked={(effortOff ? 'auto' : effort) === e.id} disabled={effortOff && e.id !== 'auto'} onClick={() => onEffort(e.id)}
                  className={cn('h-7 rounded-md text-xs font-medium transition disabled:opacity-40', (effortOff ? 'auto' : effort) === e.id ? 'bg-panel2 text-fg' : 'text-muted hover:text-fg')}>{t(e.label)}</button>
              ))}
            </div>
          </section>
          <section>
            <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted">{t('Quyền')}</p>
            {PERMISSIONS.map((p) => (
              <button key={p.id} role="menuitemradio" aria-checked={p.id === permission} onClick={() => choosePerm(p.id)}
                className={cn('flex w-full items-start gap-2.5 rounded-lg px-2 py-1.5 text-left transition hover:bg-panel2', p.id === permission && 'bg-panel2')}>
                <p.icon className={cn('mt-0.5 size-4 shrink-0', p.tone)} />
                <span className="min-w-0 flex-1"><span className="block text-sm font-medium">{t(p.label)}</span><span className="block text-xs leading-snug text-muted">{t(p.desc)}</span></span>
                {p.id === permission && <Check className="mt-0.5 size-4 shrink-0 text-accent" />}
              </button>
            ))}
            <p className="px-2 pt-1 text-[11px] text-muted">{t('Chỉ áp dụng cho hội thoại hiện tại.')}</p>
          </section>
        </div>
      )}
    </div>
  )
}
