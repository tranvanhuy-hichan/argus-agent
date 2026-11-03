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
  const t = d.totals
  const empty = t.llm_calls === 0

  return (
    <Page>
      <PageHeader title="Dashboard" subtitle="Tổng quan hoạt động của agent." action={
        <div className="w-64"><Tabs value={days} onChange={setDays} tabs={[{ id: '7', label: '7 ngày' }, { id: '30', label: '30 ngày' }, { id: '90', label: '90 ngày' }]} /></div>
      } />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat icon={MessageSquare} label="Tin nhắn" value={fmtNum(t.messages)} sub={`${t.sessions} hội thoại`} />
        <Stat icon={Coins} label="Token" value={fmtNum(t.prompt_tokens + t.completion_tokens)} sub={`${fmtNum(t.prompt_tokens)} vào · ${fmtNum(t.completion_tokens)} ra`} />
        <Stat icon={Wrench} label="Gọi tool" value={fmtNum(t.tool_calls)} sub={t.tool_errors ? `${t.tool_errors} lỗi` : 'không có lỗi'} tone={t.tool_errors ? 'var(--warn)' : undefined} />
        <Stat icon={Activity} label="Độ trễ TB / lần gọi LLM" value={`${(t.avg_latency_ms / 1000).toFixed(1)}s`} sub={`${t.llm_calls} lần gọi${t.llm_errors ? ` · ${t.llm_errors} lỗi` : ''}`} tone={t.llm_errors ? 'var(--bad)' : undefined} />
      </div>

      {empty ? (
        <Card className="mt-4 p-8 text-center text-sm text-muted">Chưa có dữ liệu trong khoảng thời gian này. Hãy <Link to="/chat" className="text-accent hover:underline">chat với agent</Link> để bắt đầu.</Card>
      ) : (
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader title="Token theo ngày" />
            <div className="h-64 p-4">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={d.series}>
                  <defs>
                    <linearGradient id="gp" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--accent)" stopOpacity={0.35} /><stop offset="100%" stopColor="var(--accent)" stopOpacity={0} /></linearGradient>
                  </defs>
                  <CartesianGrid stroke="var(--line)" vertical={false} />
                  <XAxis dataKey="date" tickFormatter={dayLabel} {...axis} />
                  <YAxis tickFormatter={fmtNum} width={40} {...axis} />
                  <Tooltip {...tip} labelFormatter={(l) => String(l)} formatter={(v, n) => [fmtNum(Number(v)), n === 'prompt' ? 'Vào' : 'Ra']} />
                  <Area isAnimationActive={false} type="monotone" dataKey="prompt" stackId="1" stroke="var(--accent)" fill="url(#gp)" strokeWidth={2} />
                  <Area isAnimationActive={false} type="monotone" dataKey="completion" stackId="1" stroke="var(--info)" fill="var(--info)" fillOpacity={0.15} strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Card>
          <Card>
            <CardHeader title="Lượt gọi LLM và tool theo ngày" />
            <div className="h-64 p-4">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={d.series}>
                  <CartesianGrid stroke="var(--line)" vertical={false} />
                  <XAxis dataKey="date" tickFormatter={dayLabel} {...axis} />
                  <YAxis allowDecimals={false} width={30} {...axis} />
                  <Tooltip {...tip} formatter={(v, n) => [String(v), n === 'calls' ? 'LLM' : 'Tool']} />
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
          <CardHeader title="Provider / model" />
          {d.by_provider.length === 0 ? <p className="p-5 text-sm text-muted">Chưa có dữ liệu.</p> : (
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-muted"><tr><th className="px-5 py-2 font-medium">Provider</th><th className="py-2 font-medium">Lần gọi</th><th className="py-2 font-medium">Token</th><th className="py-2 font-medium">Độ trễ</th><th className="px-5 py-2 text-right font-medium">Lỗi</th></tr></thead>
              <tbody>{d.by_provider.map((p) => (
                <tr key={p.provider + p.model} className="border-t border-line">
                  <td className="px-5 py-2.5"><span className="font-medium">{p.provider}</span> <span className="text-xs text-muted">{p.model}</span></td>
                  <td className="tabular-nums">{p.calls}</td><td className="tabular-nums">{fmtNum(p.tokens)}</td><td className="tabular-nums">{(p.latency / 1000).toFixed(1)}s</td>
                  <td className="px-5 text-right">{p.errors ? <Badge tone="bad">{p.errors}</Badge> : <span className="text-muted">0</span>}</td>
                </tr>))}</tbody>
            </table>
          )}
        </Card>
        <Card>
          <CardHeader title="Tool dùng nhiều nhất" />
          {d.top_tools.length === 0 ? <p className="p-5 text-sm text-muted">Chưa có dữ liệu.</p> : (
            <ul className="p-2">{d.top_tools.map((x) => (
              <li key={x.name} className="flex items-center justify-between rounded-lg px-3 py-2 text-sm hover:bg-panel2">
                <span className="font-mono text-[13px]">{x.name}</span>
                <span className="flex items-center gap-2 tabular-nums">{x.errors > 0 && <Badge tone="bad">{x.errors} lỗi</Badge>}{x.n}</span>
              </li>))}</ul>
          )}
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card className="p-5">
          <div className="flex items-center gap-2 text-sm font-semibold"><Puzzle className="size-4 text-muted" />Skills</div>
          <p className="mt-3 text-3xl font-semibold tabular-nums">{d.skills.active}<span className="text-base font-normal text-muted"> / {d.skills.total} đang hoạt động</span></p>
          {d.skills.needs_setup > 0 && <p className="mt-1 text-sm text-warn">{d.skills.needs_setup} skill cần thiết lập</p>}
          <Link to="/skills" className="mt-3 inline-block text-sm text-accent hover:underline">Quản lý skills →</Link>
        </Card>
        <Card className="p-5">
          <div className="flex items-center gap-2 text-sm font-semibold"><Timer className="size-4 text-muted" />Automations</div>
          <p className="mt-3 text-3xl font-semibold tabular-nums">{d.automations.enabled}<span className="text-base font-normal text-muted"> / {d.automations.total} đang bật</span></p>
          <p className="mt-1 flex items-center gap-1 text-sm text-muted"><Clock className="size-3.5" />Lần chạy tới: {fmtDateTime(d.automations.next)}</p>
          <Link to="/automations" className="mt-3 inline-block text-sm text-accent hover:underline">Quản lý automations →</Link>
        </Card>
        <Card>
          <CardHeader title="Hội thoại gần đây" />
          <ul className="p-2">{d.recent_sessions.length === 0 && <li className="px-3 py-2 text-sm text-muted">Chưa có.</li>}{d.recent_sessions.map((s) => (
            <li key={s.id}><Link to="/chat" className="flex items-center justify-between gap-2 rounded-lg px-3 py-2 text-sm hover:bg-panel2"><span className="truncate">{s.title}</span><span className="shrink-0 text-xs text-muted">{timeAgo(s.updated)}</span></Link></li>))}</ul>
        </Card>
      </div>
    </Page>
  )
}
