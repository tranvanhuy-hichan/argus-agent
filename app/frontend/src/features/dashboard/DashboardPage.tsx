import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Activity, Clock, Coins, MessageSquare, Puzzle, Timer, Wrench, type LucideIcon } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Card, CardHeader } from '@/components/ui/Card'
import { ErrorNote, Loading, Page, PageHeader } from '@/components/ui/misc'
import { Tabs } from '@/components/ui/Tabs'
import { useDashboard } from '@/lib/queries'
import { fmtDateTime, fmtNum, timeAgo } from '@/lib/utils'
import { t } from '@/lib/i18n.ts'
import { T } from '@/lib/T.tsx'

function Stat({ icon: Icon, label, value, sub, tone }: { icon: LucideIcon; label: string; value: ReactNode; sub?: ReactNode; tone?: string }) {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-2 text-xs font-medium text-muted"><Icon className="size-3.5" />{label}</div>
      <p className="mt-2 text-2xl font-semibold tabular-nums" style={tone ? { color: tone } : undefined}>{value}</p>
      {sub && <p className="mt-0.5 text-xs text-muted">{sub}</p>}
    </Card>
  )
}

const axis = { stroke: 'var(--muted)', fontSize: 11, tickLine: false, axisLine: false } as const
const tip = { contentStyle: { background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: 8, fontSize: 12 }, labelStyle: { color: 'var(--muted)' }, cursor: { fill: 'var(--panel-2)' } }
const dayLabel = (d: string) => d.slice(5).replace('-', '/')

export function DashboardPage() {
  const [days, setDays] = useState('7')
  const q = useDashboard(Number(days))
  if (q.error) return <Page><ErrorNote error={q.error} /></Page>
  if (!q.data) return <Loading />
  const d = q.data
  const tot = d.totals
  const empty = tot.llm_calls === 0

  return (
    <Page>
      <PageHeader title={t('Bảng điều khiển')} action={
        <div className="w-64"><Tabs value={days} onChange={setDays} tabs={[{ id: '7', label: t('{n} ngày', { n: 7 }) }, { id: '30', label: t('{n} ngày', { n: 30 }) }, { id: '90', label: t('{n} ngày', { n: 90 }) }]} /></div>
      } />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat icon={MessageSquare} label={t('Tin nhắn')} value={fmtNum(tot.messages)} sub={t('{n} hội thoại', { n: tot.sessions })} />
        <Stat icon={Coins} label="Token" value={fmtNum(tot.prompt_tokens + tot.completion_tokens)} sub={t('{in} vào · {out} ra', { in: fmtNum(tot.prompt_tokens), out: fmtNum(tot.completion_tokens) }) + (tot.cost > 0 ? ` · ≈ $${tot.cost.toFixed(4)}` : '')} />
        <Stat icon={Wrench} label={t('Gọi tool')} value={fmtNum(tot.tool_calls)} sub={tot.tool_errors ? t('{n} lỗi', { n: tot.tool_errors }) : t('không có lỗi')} tone={tot.tool_errors ? 'var(--warn)' : undefined} />
        <Stat icon={Activity} label={t('Độ trễ TB / lần gọi LLM')} value={`${(tot.avg_latency_ms / 1000).toFixed(1)}s`} sub={t('{n} lần gọi', { n: tot.llm_calls }) + (tot.llm_errors ? ` · ${t('{n} lỗi', { n: tot.llm_errors })}` : '')} tone={tot.llm_errors ? 'var(--bad)' : undefined} />
      </div>

      {empty ? (
        <Card className="mt-4 p-8 text-center text-sm text-muted"><T k="Chưa có dữ liệu trong khoảng thời gian này. Hãy {link} để bắt đầu." v={{ link: <Link to="/chat" className="text-accent hover:underline">{t('chat với agent')}</Link> }} /></Card>
      ) : (
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader title={t('Token theo ngày')} />
            <div className="h-64 p-4">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={d.series}>
                  <defs>
                    <linearGradient id="gp" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--accent)" stopOpacity={0.35} /><stop offset="100%" stopColor="var(--accent)" stopOpacity={0} /></linearGradient>
                  </defs>
                  <CartesianGrid stroke="var(--line)" vertical={false} />
                  <XAxis dataKey="date" tickFormatter={dayLabel} {...axis} />
                  <YAxis tickFormatter={fmtNum} width={40} {...axis} />
                  <Tooltip {...tip} labelFormatter={(l) => String(l)} formatter={(v, n) => [fmtNum(Number(v)), n === 'prompt' ? t('Vào') : t('Ra')]} />
                  <Area isAnimationActive={false} type="monotone" dataKey="prompt" stackId="1" stroke="var(--accent)" fill="url(#gp)" strokeWidth={2} />
                  <Area isAnimationActive={false} type="monotone" dataKey="completion" stackId="1" stroke="var(--info)" fill="var(--info)" fillOpacity={0.15} strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Card>
          <Card>
            <CardHeader title={t('Lượt gọi LLM và tool theo ngày')} />
            <div className="h-64 p-4">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={d.series}>
                  <CartesianGrid stroke="var(--line)" vertical={false} />
                  <XAxis dataKey="date" tickFormatter={dayLabel} {...axis} />
                  <YAxis allowDecimals={false} width={30} {...axis} />
                  <Tooltip {...tip} formatter={(v, n) => [String(v), n === 'calls' ? 'LLM' : t('Công cụ')]} />
                  <Bar isAnimationActive={false} dataKey="calls" fill="var(--accent)" radius={[4, 4, 0, 0]} />
                  <Bar isAnimationActive={false} dataKey="tools" fill="var(--info)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </div>
      )}

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title={t('Nhà cung cấp / model')} />
          {d.by_provider.length === 0 ? <p className="p-5 text-sm text-muted">{t('Chưa có dữ liệu.')}</p> : (
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-muted"><tr><th className="px-5 py-2 font-medium">{t('Nhà cung cấp')}</th><th className="py-2 font-medium">{t('Lần gọi')}</th><th className="py-2 font-medium">Token</th><th className="py-2 font-medium">{t('Độ trễ')}</th><th className="py-2 font-medium">{t('Chi phí ≈')}</th><th className="px-5 py-2 text-right font-medium">{t('Lỗi')}</th></tr></thead>
              <tbody>{d.by_provider.map((p) => (
                <tr key={p.provider + p.model} className="border-t border-line">
                  <td className="px-5 py-2.5"><span className="font-medium">{p.provider}</span> <span className="text-xs text-muted">{p.model}</span></td>
                  <td className="tabular-nums">{p.calls}</td><td className="tabular-nums">{fmtNum(p.tokens)}</td><td className="tabular-nums">{(p.latency / 1000).toFixed(1)}s</td><td className="tabular-nums text-muted">{p.cost > 0 ? `$${p.cost.toFixed(4)}` : '—'}</td>
                  <td className="px-5 text-right">{p.errors ? <Badge tone="bad">{p.errors}</Badge> : <span className="text-muted">0</span>}</td>
                </tr>))}</tbody>
            </table>
          )}
        </Card>
        <Card>
          <CardHeader title={t('Tool dùng nhiều nhất')} />
          {d.top_tools.length === 0 ? <p className="p-5 text-sm text-muted">{t('Chưa có dữ liệu.')}</p> : (
            <ul className="p-2">{d.top_tools.map((x) => (
              <li key={x.name} className="flex items-center justify-between rounded-lg px-3 py-2 text-sm hover:bg-panel2">
                <span className="font-mono text-[13px]">{x.name}</span>
                <span className="flex items-center gap-2 tabular-nums">{x.errors > 0 && <Badge tone="bad">{t('{n} lỗi', { n: x.errors })}</Badge>}{x.n}</span>
              </li>))}</ul>
          )}
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card className="p-5">
          <div className="flex items-center gap-2 text-sm font-semibold"><Puzzle className="size-4 text-muted" />{t('Kỹ năng')}</div>
          <p className="mt-3 text-3xl font-semibold tabular-nums">{d.skills.active}<span className="text-base font-normal text-muted"> {t('/ {n} đang hoạt động', { n: d.skills.total })}</span></p>
          {d.skills.needs_setup > 0 && <p className="mt-1 text-sm text-warn">{t('{n} skill cần thiết lập', { n: d.skills.needs_setup })}</p>}
          <Link to="/skills" className="mt-3 inline-block text-sm text-accent hover:underline">{t('Quản lý skills →')}</Link>
        </Card>
        <Card className="p-5">
          <div className="flex items-center gap-2 text-sm font-semibold"><Timer className="size-4 text-muted" />{t('Tự động hóa')}</div>
          <p className="mt-3 text-3xl font-semibold tabular-nums">{d.automations.enabled}<span className="text-base font-normal text-muted"> {t('/ {n} đang bật', { n: d.automations.total })}</span></p>
          <p className="mt-1 flex items-center gap-1 text-sm text-muted"><Clock className="size-3.5" />{t('Lần chạy tới: {when}', { when: fmtDateTime(d.automations.next) })}</p>
          <Link to="/automations" className="mt-3 inline-block text-sm text-accent hover:underline">{t('Quản lý automations →')}</Link>
        </Card>
        <Card>
          <CardHeader title={t('Hội thoại gần đây')} />
          <ul className="p-2">{d.recent_sessions.length === 0 && <li className="px-3 py-2 text-sm text-muted">{t('Chưa có.')}</li>}{d.recent_sessions.map((s) => (
            <li key={s.id}><Link to={`/chat?session=${s.id}`} className="flex items-center justify-between gap-2 rounded-lg px-3 py-2 text-sm hover:bg-panel2"><span className="truncate">{s.title}</span><span className="shrink-0 text-xs text-muted">{timeAgo(s.updated)}</span></Link></li>))}</ul>
        </Card>
      </div>
    </Page>
  )
}
