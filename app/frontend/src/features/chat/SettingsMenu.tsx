import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Check, Cpu, Gauge } from 'lucide-react'
import { LimitsBars } from '@/features/providers/LimitsBars'
import { t } from '@/lib/i18n.ts'
import { cn } from '@/lib/utils'
import type { ProviderOption } from './Composer'
import { EFFORTS, PERMISSIONS, type Effort, type Permission } from './permissions'

/** Nút nhỏ mở một bảng chọn riêng (đóng khi bấm ra ngoài hoặc nhấn Esc). */
function Pop({ button, label, active, disabled, title, children, width = 'w-72' }: { button: ReactNode; label: string; active?: boolean; disabled?: boolean; title?: string; children: (close: () => void, open: boolean) => ReactNode; width?: string }) {
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const down = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false) }
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', down)
    document.addEventListener('keydown', key)
    return () => { document.removeEventListener('mousedown', down); document.removeEventListener('keydown', key) }
  }, [open])
  return (
    <div ref={box} className="relative">
      <button type="button" onClick={() => setOpen(!open)} disabled={disabled} aria-haspopup="dialog" aria-expanded={open} aria-label={label} title={title ?? label}
        className={cn('flex h-8 max-w-40 items-center gap-1.5 rounded-full px-2.5 text-sm transition disabled:opacity-40', open || active ? 'bg-panel2 text-fg' : 'text-muted hover:bg-panel2 hover:text-fg')}>{button}</button>
      {open && <div role="dialog" aria-label={label} className={cn('fade-in absolute bottom-full right-0 z-30 mb-2 max-w-[90vw] rounded-xl border border-line bg-panel p-1.5 shadow-2xl', width)}>{children(() => setOpen(false), open)}</div>}
    </div>
  )
}

const Row = ({ on, onClick, children, hint }: { on: boolean; onClick: () => void; children: ReactNode; hint?: string }) => (
  <button type="button" role="menuitemradio" aria-checked={on} onClick={onClick} title={hint}
    className={cn('flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm transition hover:bg-panel2', on && 'bg-panel2')}>{children}{on && <Check className="ml-auto size-4 shrink-0 text-accent" />}</button>
)

/** Các nút tuỳ chọn của hội thoại, mỗi nút một bảng nhỏ: model, hạn mức, mức suy luận và quyền. */
export function SettingsMenu({ providers, provider, onProvider, effort, onEffort, effortOff, permission, onPermission }: {
  providers: ProviderOption[]; provider: string; onProvider: (id: string) => void
  effort: Effort; onEffort: (e: Effort) => void; effortOff: boolean
  permission: Permission; onPermission: (p: Permission) => void
}) {
  const perm = PERMISSIONS.find((x) => x.id === permission) ?? PERMISSIONS[0]
  const eff = EFFORTS.find((e) => e.id === (effortOff ? 'auto' : effort)) ?? EFFORTS[0]
  const choosePerm = (id: Permission) => {
    if (id === 'full' && !confirm(t('Toàn quyền: agent sẽ chạy lệnh và đọc/ghi file mà không hỏi bạn. Chỉ bật khi bạn tin tưởng yêu cầu của mình. Tiếp tục?'))) return false
    onPermission(id)
    return true
  }
  return (
    <div className="flex items-center gap-0.5">
      <Pop label={t('Mô hình AI')} button={<><Cpu className="size-4 shrink-0" /><span className="truncate">{provider}</span></>} width="w-80">
        {(close) => (
          <div role="radiogroup" aria-label={t('Mô hình AI')}>
            {providers.map((x) => (
              <Row key={x.id} on={x.id === provider} onClick={() => { onProvider(x.id); close() }}>
                <span className="min-w-0"><span className="block truncate font-medium">{x.id}</span><span className="block truncate font-mono text-xs text-muted">{x.model}</span></span>
              </Row>
            ))}
          </div>
        )}
      </Pop>

      <Pop label={t('Hạn mức')} button={<Gauge className="size-4" />} width="w-80">
        {(_close, open) => <div className="p-2"><LimitsBars name={provider} compact enabled={open} /></div>}
      </Pop>

      <Pop label={t('Mức suy luận')} disabled={effortOff} title={effortOff ? t('Chưa hỗ trợ với provider Anthropic') : t('Mức suy luận')} button={<span>{t(eff.label)}</span>} width="w-44">
        {(close) => (
          <div role="radiogroup" aria-label={t('Mức suy luận')}>
            {EFFORTS.map((e) => <Row key={e.id} on={e.id === eff.id} onClick={() => { onEffort(e.id); close() }}>{t(e.label)}</Row>)}
          </div>
        )}
      </Pop>

      <Pop label={t('Quyền')} active={permission !== 'default'} button={<><perm.icon className={cn('size-4 shrink-0', perm.tone)} /><span className={cn('truncate', permission !== 'default' && perm.tone)}>{t(perm.label)}</span></>} width="w-56">
        {(close) => (
          <div role="radiogroup" aria-label={t('Quyền')}>
            {PERMISSIONS.map((p) => (
              <Row key={p.id} on={p.id === permission} hint={t(p.desc)} onClick={() => { if (choosePerm(p.id)) close() }}>
                <p.icon className={cn('size-4 shrink-0', p.tone)} />{t(p.label)}
              </Row>
            ))}
            <p className="px-2.5 pb-1 pt-1.5 text-[11px] text-muted">{t('Chỉ áp dụng cho hội thoại hiện tại.')}</p>
          </div>
        )}
      </Pop>
    </div>
  )
}
