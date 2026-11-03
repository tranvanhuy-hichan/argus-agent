import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { t } from '@/lib/i18n.ts'
import { fmtNum } from '@/lib/utils'
import type { Dashboard } from '@/lib/types'

type Series = Dashboard['series']
const axis = { stroke: 'var(--muted)', fontSize: 11, tickLine: false, axisLine: false } as const
const tip = { contentStyle: { background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: 8, fontSize: 12 }, labelStyle: { color: 'var(--muted)' }, cursor: { fill: 'var(--panel-2)' } }
const day = (d: string) => d.slice(5).replace('-', '/')

/** Duong ve nho (khong truc) trong the so lieu. */
export function Spark({ data, k, color = 'var(--accent)' }: { data: Series; k: keyof Series[number]; color?: string }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
        <Area isAnimationActive={false} type="monotone" dataKey={k} stroke={color} fill={color} fillOpacity={0.15} strokeWidth={1.75} />
      </AreaChart>
    </ResponsiveContainer>
  )
}

export function ActivityChart({ data }: { data: Series }) {
  const tokens = data.map((d) => ({ ...d, total: d.prompt + d.completion }))
  return (
    <div className="grid h-full gap-4 sm:grid-cols-2">
      <div className="min-h-0">
        <p className="mb-1 text-xs text-muted">{t('Token theo ngày')}</p>
        <ResponsiveContainer width="100%" height="90%">
          <AreaChart data={tokens}>
            <defs><linearGradient id="hg" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--accent)" stopOpacity={0.35} /><stop offset="100%" stopColor="var(--accent)" stopOpacity={0} /></linearGradient></defs>
            <CartesianGrid stroke="var(--line)" vertical={false} />
            <XAxis dataKey="date" tickFormatter={day} {...axis} />
            <YAxis tickFormatter={fmtNum} width={38} {...axis} />
            <Tooltip {...tip} formatter={(v) => [fmtNum(Number(v)), t('Token theo ngày')]} />
            <Area isAnimationActive={false} type="monotone" dataKey="total" stroke="var(--accent)" fill="url(#hg)" strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div className="min-h-0">
        <p className="mb-1 text-xs text-muted">{t('Lượt gọi model và tool')}</p>
        <ResponsiveContainer width="100%" height="90%">
          <BarChart data={data}>
            <CartesianGrid stroke="var(--line)" vertical={false} />
            <XAxis dataKey="date" tickFormatter={day} {...axis} />
            <YAxis allowDecimals={false} width={28} {...axis} />
            <Tooltip {...tip} formatter={(v, n) => [String(v), n === 'calls' ? t('Lượt gọi model') : t('Lần gọi tool')]} />
            <Bar isAnimationActive={false} dataKey="calls" fill="var(--accent)" radius={[4, 4, 0, 0]} />
            <Bar isAnimationActive={false} dataKey="tools" fill="var(--info)" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
