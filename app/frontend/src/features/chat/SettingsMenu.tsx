import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Brain, Check, Gauge, RotateCcw } from 'lucide-react'
import { BrandIcon, detectBrand } from '@/components/ui/BrandIcon'
import { LimitsBars } from '@/features/providers/LimitsBars'
import { t } from '@/lib/i18n.ts'
import { cn } from '@/lib/utils'
import type { ProviderOption } from './Composer'
import { EFFORTS, PERMISSIONS, type Effort, type Permission } from './permissions'

/** Nút nhỏ mở một bảng chọn riêng (đóng khi bấm ra ngoài hoặc nhấn Esc). */
function Pop({ button, label, active, disabled, title, children, width = 'w-72', className }: { button: ReactNode; label: string; active?: boolean; disabled?: boolean; title?: string; children: (close: () => void, open: boolean) => ReactNode; width?: string; className?: string }) {
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
        className={cn('flex h-8 max-w-56 items-center gap-1.5 rounded-full px-2.5 text-sm transition disabled:opacity-40', open || active ? 'bg-panel2 text-fg' : 'text-muted hover:bg-panel2 hover:text-fg', className)}>{button}</button>
      {open && <div role="dialog" aria-label={label} className={cn('fade-in absolute bottom-full right-0 z-30 mb-2 max-w-[90vw] rounded-xl border border-line bg-panel p-1.5 shadow-2xl', width)}>{children(() => setOpen(false), open)}</div>}
    </div>
  )
}

const Row = ({ on, onClick, children, hint }: { on: boolean; onClick: () => void; children: ReactNode; hint?: string }) => (
  <button type="button" role="menuitemradio" aria-checked={on} onClick={onClick} title={hint}
    className={cn('flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm transition hover:bg-panel2', on && 'bg-panel2')}>{children}{on && <Check className="ml-auto size-4 shrink-0 text-accent" />}</button>
)

/** Các nút tuỳ chọn của hội thoại, mỗi nút một bảng nhỏ: model, hạn mức, mức suy luận và quyền. */
export function SettingsMenu({ providers, provider, onProvider, effort, onEffort, effortOff, permission, onPermission, temperature = 0.7, onTemperature, maxTokens = 4096, onMaxTokens }: {
  providers: ProviderOption[]; provider: string; onProvider: (id: string) => void
  effort: Effort; onEffort: (e: Effort) => void; effortOff: boolean
  permission: Permission; onPermission: (p: Permission) => void
  temperature?: number; onTemperature?: (t: number) => void
  maxTokens?: number; onMaxTokens?: (m: number) => void
}) {
  const perm = PERMISSIONS.find((x) => x.id === permission) ?? PERMISSIONS[0]
  const eff = EFFORTS.find((e) => e.id === (effortOff ? 'auto' : effort)) ?? EFFORTS[0]
  const currentProvider = providers.find((x) => x.id === provider)
  const modelName = currentProvider?.model || provider
  const brand = detectBrand(currentProvider || provider)

  const choosePerm = (id: Permission) => {
    if (id === 'full' && !confirm(t('Toàn quyền: agent sẽ chạy lệnh và đọc/ghi file mà không hỏi bạn. Chỉ bật khi bạn tin tưởng yêu cầu của mình. Tiếp tục?'))) return false
    onPermission(id)
    return true
  }
  return (
    <div className="flex items-center gap-0.5">
      {/* Nút 1: Chọn Model */}
      <Pop label={t('Mô hình AI')} title={`${provider} · ${modelName}`} button={<><BrandIcon brand={brand} className="size-4 shrink-0" /><span className="truncate">{modelName}</span></>} width="w-80">
        {(close) => (
          <div role="radiogroup" aria-label={t('Mô hình AI')}>
            {providers.map((x) => (
              <Row key={x.id} on={x.id === provider} onClick={() => { onProvider(x.id); close() }}>
                <span className="grid size-6 shrink-0 place-items-center rounded bg-panel2">
                  <BrandIcon brand={detectBrand(x)} className="size-4" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{x.model || x.id}</span>
                  <span className="block truncate font-mono text-xs text-muted">{x.id}</span>
                </span>
              </Row>
            ))}
          </div>
        )}
      </Pop>

      {/* Nút 2: Mức suy luận & Tham số sinh (Nhiệt độ + Max Tokens) */}
      <Pop
        label={t('Mức suy luận & Tham số')}
        disabled={effortOff}
        title={effortOff ? t('Chưa hỗ trợ với provider Anthropic') : `${t('Mức suy luận & Tham số')} · ${t(eff.label)}`}
        button={
          <>
            <Brain className={cn('size-4 shrink-0', effort === 'thinking' && 'text-accent animate-pulse')} />
            <span className={cn('truncate', effort === 'thinking' && 'text-accent font-medium')}>
              {effort === 'thinking' ? t('Suy nghĩ') : t(eff.label)}
            </span>
          </>
        }
        width="w-80"
      >
        {() => (
          <div className="space-y-3 p-1">
            {/* Mục 1: Mức suy luận */}
            <div>
              <p className="px-2.5 pb-1 pt-1 text-[11px] font-semibold uppercase tracking-wider text-muted">{t('Mức suy luận')}</p>
              <div role="radiogroup" aria-label={t('Mức suy luận')} className="space-y-0.5">
                {EFFORTS.map((e) => (
                  <Row key={e.id} on={e.id === eff.id} onClick={() => onEffort(e.id)}>
                    {e.id === 'thinking' && <Brain className="size-3.5 shrink-0 text-accent" />}
                    <div className="min-w-0 flex-1">
                      <span className="font-medium">{t(e.label)}</span>
                      {e.id === 'thinking' && <span className="ml-1.5 text-[11px] text-muted font-normal">({t('Kèm thẻ suy nghĩ')})</span>}
                    </div>
                  </Row>
                ))}
              </div>
            </div>

            {/* Mục 2: Tham số sinh */}
            {onTemperature && onMaxTokens && (
              <div className="border-t border-line px-2.5 pt-2.5 space-y-2.5 text-xs">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-muted">{t('Tham số sinh')}</p>
                <div>
                  <div className="flex items-center justify-between pb-1">
                    <span className="font-medium text-fg">{t('Nhiệt độ (Temperature)')}</span>
                    <span className="rounded bg-panel2 px-1.5 py-0.5 font-mono font-medium text-accent">{temperature.toFixed(2)}</span>
                  </div>
                  <input
                    type="range" min="0" max="1.5" step="0.05"
                    value={temperature}
                    onChange={(e) => onTemperature(parseFloat(e.target.value))}
                    className="h-1.5 w-full cursor-pointer accent-accent"
                  />
                  <div className="mt-1 flex justify-between text-[10px] text-muted">
                    <span>0.0 ({t('Chính xác')})</span>
                    <span>0.6 ({t('Suy luận')})</span>
                    <span>1.2+ ({t('Sáng tạo')})</span>
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between pb-1">
                    <span className="font-medium text-fg">{t('Độ dài tối đa (Max Tokens)')}</span>
                    <span className="rounded bg-panel2 px-1.5 py-0.5 font-mono font-medium text-accent">{maxTokens.toLocaleString()}</span>
                  </div>
                  <div className="grid grid-cols-4 gap-1 pt-1">
                    {[1024, 2048, 4096, 8192].map((n) => (
                      <button
                        key={n}
                        type="button"
                        onClick={() => onMaxTokens(n)}
                        className={cn('rounded py-1 text-center font-mono text-xs transition', maxTokens === n ? 'bg-accent text-accent-fg font-medium' : 'bg-panel2 text-muted hover:text-fg')}
                      >
                        {n >= 1000 ? `${n / 1024}k` : n}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex justify-end border-t border-line/60 pt-2">
                  <button
                    type="button"
                    onClick={() => { onTemperature(0.7); onMaxTokens(4096) }}
                    className="flex items-center gap-1 text-[11px] text-muted hover:text-fg"
                  >
                    <RotateCcw className="size-3" />
                    {t('Khôi phục mặc định')}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </Pop>

      {/* Nút 3: Quyền hạn & Hạn mức token */}
      <Pop
        label={t('Quyền & Hạn mức')}
        active={permission !== 'default'}
        title={`${t('Quyền hạn & Hạn mức')} · ${t(perm.label)}`}
        button={
          <>
            <perm.icon className={cn('size-4 shrink-0', perm.tone)} />
            <span className={cn('truncate', permission !== 'default' && perm.tone)}>{t(perm.label)}</span>
          </>
        }
        width="w-72"
      >
        {(close, open) => (
          <div className="space-y-3 p-1">
            {/* Mục 1: Quyền hạn */}
            <div>
              <p className="px-2.5 pb-1 pt-1 text-[11px] font-semibold uppercase tracking-wider text-muted">{t('Quyền hạn của Agent')}</p>
              <div role="radiogroup" aria-label={t('Quyền')} className="space-y-0.5">
                {PERMISSIONS.map((p) => (
                  <Row key={p.id} on={p.id === permission} hint={t(p.desc)} onClick={() => { if (choosePerm(p.id)) close() }}>
                    <p.icon className={cn('size-4 shrink-0', p.tone)} />
                    <div className="min-w-0 flex-1">
                      <div className="font-medium">{t(p.label)}</div>
                      <div className="text-[11px] text-muted leading-tight">{t(p.desc)}</div>
                    </div>
                  </Row>
                ))}
              </div>
              <p className="px-2.5 pt-1 text-[11px] text-muted">{t('Chỉ áp dụng cho hội thoại hiện tại.')}</p>
            </div>

            {/* Mục 2: Hạn mức token */}
            <div className="border-t border-line px-2.5 pt-2.5">
              <div className="flex items-center justify-between pb-1.5">
                <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted">
                  <Gauge className="size-3.5" />
                  {t('Hạn mức & Quota')}
                </p>
                <span className="font-mono text-[11px] text-muted">{provider}</span>
              </div>
              <LimitsBars name={provider} compact enabled={open} />
            </div>
          </div>
        )}
      </Pop>
    </div>
  )
}
