import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { t } from '@/lib/i18n.ts'
import type { ProviderLimits } from '@/lib/types'
import { cn, fmtNum } from '@/lib/utils'

const tone = (used: number) => (used >= 90 ? 'bg-bad' : used >= 70 ? 'bg-warn' : 'bg-accent')
const noZone = (s: string) => s.replace(/\s*\([^)]*\)\s*$/, '') // bỏ phần "(Asia/Bangkok)" cho gọn

/** Một thanh đo: nhãn bên trái, giá trị bên phải, thanh tiến độ ở dưới. */
function Bar({ label, value, pct, color, title }: { label: string; value: string; pct: number; color: string; title?: string }) {
  return (
    <div title={title}>
      <div className="mb-1 flex items-baseline justify-between gap-2"><span className="text-fg">{label}</span><span className="tabular-nums text-muted">{value}</span></div>
      <div className="h-1.5 overflow-hidden rounded-full bg-panel2" role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemax={100} aria-label={label}>
        <div className={cn('h-full rounded-full transition-all', color)} style={{ width: `${Math.max(pct > 0 ? 2 : 0, Math.min(100, pct))}%` }} />
      </div>
    </div>
  )
}

/** Hạn mức một model dạng thanh đo: phiên 5 giờ và tuần của gói thuê bao (nếu có), cùng phần Argus đã dùng. */
export function LimitsBars({ name, compact = false, enabled = true }: { name: string; compact?: boolean; enabled?: boolean }) {
  const q = useQuery({ queryKey: ['limits', name], queryFn: () => api.get<ProviderLimits>(`/api/providers/${name}/limits`), enabled, staleTime: 60_000, refetchInterval: 120_000 })
  const d = q.data
  if (q.isLoading) return <p className="text-xs text-muted">{t('Đang lấy hạn mức…')}</p>
  if (!d) return null
  const wins = d.official ? (d.limits?.windows ?? []) : []
  const off = [wins.find((w) => w.kind === 'session'), wins.find((w) => w.kind !== 'session' && (!w.model || w.model === 'all models')) ?? wins.find((w) => w.kind !== 'session')]
  const rows = [[t('5 giờ'), d.argus.h5, off[0]], [t('7 ngày'), d.argus.d7, off[1]]] as const
  return (
    <div className={cn('space-y-2.5', compact ? 'text-[11px]' : 'text-xs')}>
      {rows.map(([label, u, w]) => {
        const own = t('{n} lượt, {p}% tổng token của Argus', { n: u.calls, p: Math.round(u.share * 100) })
        if (w) return <Bar key={label} label={label} value={t('{u}% đã dùng', { u: w.used })} pct={w.used} color={tone(w.used)} title={[w.resets ? t('Làm mới {when}', { when: noZone(w.resets) }) : '', `Argus: ${fmtNum(u.tokens)} token`].filter(Boolean).join(' · ')} />
        return <Bar key={label} label={label} value={`${fmtNum(u.tokens)} token`} pct={u.share * 100} color="bg-info" title={own} />
      })}
    </div>
  )
}
