import { lazy, Suspense, useState, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  Activity, ArrowRight, ArrowUp, Bell, Bot, CheckCircle2, Circle, Clock, Coins, Gauge, HeartPulse, MessageSquare, Plug, Puzzle, Send, ShieldCheck, Sparkles, Wrench, type LucideIcon,
} from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Card, CardHeader } from '@/components/ui/Card'
import { Loading, Page } from '@/components/ui/misc'
import { api } from '@/lib/api'
import { t } from '@/lib/i18n.ts'
import { useConfig, useDashboard, useHeartbeat, useJobs, useMcp, useSkills } from '@/lib/queries'
import type { AuditItem, NotificationItem, TelegramStatus } from '@/lib/types'
import { cn, fmtDateTime, fmtNum, timeAgo } from '@/lib/utils'

// recharts nang: chi tai khi can, khong lam cham lan mo dau
const Spark = lazy(() => import('./HomeCharts').then((m) => ({ default: m.Spark })))
const ActivityChart = lazy(() => import('./HomeCharts').then((m) => ({ default: m.ActivityChart })))

const Dot = ({ tone }: { tone: 'ok' | 'warn' | 'bad' | 'off' }) => (
  <span className={cn('inline-block size-2 shrink-0 rounded-full', tone === 'ok' && 'bg-ok', tone === 'warn' && 'bg-warn', tone === 'bad' && 'bg-bad', tone === 'off' && 'bg-muted/50')} aria-hidden />
)

function Kpi({ icon: Icon, label, value, sub, chart, tone }: { icon: LucideIcon; label: string; value: ReactNode; sub?: ReactNode; chart?: ReactNode; tone?: string }) {
  return (
    <Card className="relative overflow-hidden p-4">
      <div className="flex items-center gap-2 text-xs font-medium text-muted"><Icon className="size-3.5" />{label}</div>
      <p className="mt-2 text-2xl font-semibold tabular-nums" style={tone ? { color: tone } : undefined}>{value}</p>
      {sub && <p className="mt-0.5 text-xs text-muted">{sub}</p>}
      {chart && <div className="pointer-events-none absolute inset-x-0 bottom-0 h-10 opacity-90">{chart}</div>}
    </Card>
  )
}

function Row({ label, value, tone, to }: { label: string; value: ReactNode; tone: 'ok' | 'warn' | 'bad' | 'off'; to?: string }) {
  const inner = (
    <>
      <span className="flex items-center gap-2.5 text-sm"><Dot tone={tone} />{label}</span>
      <span className="truncate text-right text-sm text-muted">{value}</span>
    </>
  )
  const cls = 'flex items-center justify-between gap-4 border-b border-line px-5 py-2.5 last:border-b-0'
  return to ? <Link to={to} className={cn(cls, 'transition hover:bg-panel2')}>{inner}</Link> : <div className={cls}>{inner}</div>
}

const suggestions = () => [t('Tóm tắt tin công nghệ mới nhất hôm nay'), t('Viết script Python xử lý file CSV'), t('Kiểm tra dung lượng đĩa của máy'), t('Liệt kê việc tôi nên làm hôm nay')]

export function HomePage() {
  const nav = useNavigate()
  const cfg = useConfig()
  const dash = useDashboard(7)
  const skills = useSkills()
  const mcp = useMcp()
  const hb = useHeartbeat()
  const jobs = useJobs()
  const channels = useQuery({ queryKey: ['channels'], queryFn: () => api.get<{ telegram: TelegramStatus }>('/api/channels') })
  const inbox = useQuery({ queryKey: ['notifications'], queryFn: () => api.get<{ items: NotificationItem[]; unread: number }>('/api/notifications') })
  const audit = useQuery({ queryKey: ['audit-home'], queryFn: () => api.get<{ total: number; items: AuditItem[] }>('/api/audit?limit=6'), refetchInterval: 15_000 })
  const [text, setText] = useState('')
  const [checked, setChecked] = useState(false)
  const def = cfg.data?.config.default_provider
  const health = useMutation({ mutationFn: () => api.post<{ ok: boolean; latency_ms?: number }>(`/api/providers/${def}/test`, {}) })

  if (!cfg.data || !dash.data) return <Loading />
  const c = cfg.data.config
  const d = dash.data
  const go = (prompt?: string) => nav('/chat', { state: prompt ? { prompt } : null })
  const hr = new Date().getHours()
  const greet = hr < 11 ? t('Chào buổi sáng') : hr < 18 ? t('Chào buổi chiều') : t('Chào buổi tối')

  const tg = channels.data?.telegram
  const mcpList = mcp.data ?? []
  const mcpOk = mcpList.filter((s) => s.status === 'connected').length
  const cloud = Object.values(c.providers).some((p) => p.type === 'anthropic' || !/localhost|127\.0\.0\.1/.test(p.base_url))
  const steps: { done: boolean; label: string; to: string }[] = [
    { done: cloud, label: t('Thêm một model mạnh hơn (cloud)'), to: '/providers' },
    { done: (skills.data ?? []).some((s) => s.origin), label: t('Cài một skill từ ClawHub'), to: '/skills?tab=discover' },
    { done: !!tg?.running, label: t('Kết nối Telegram để nhắn từ điện thoại'), to: '/integrations?tab=channels' },
    { done: c.heartbeat.enabled, label: t('Bật heartbeat để agent chủ động báo tin'), to: '/automations' },
    { done: c.auth.has_password, label: t('Đặt mật khẩu cho giao diện'), to: '/settings?tab=security' },
    { done: mcpList.length > 0, label: t('Nối một MCP server của bạn'), to: '/integrations' },
    { done: c.agent.exec_sandbox === 'docker', label: t('Bật sandbox Docker cho lệnh shell'), to: '/settings?tab=security' },
  ]
  const doneCount = steps.filter((s) => s.done).length
  const next = jobs.data?.filter((j) => j.enabled && j.next_run).sort((a, b) => (a.next_run ?? 0) - (b.next_run ?? 0)).slice(0, 3) ?? []
  const decisionTone = { approved: 'ok', denied: 'bad', auto: 'neutral' } as const

  return (
    <Page>
      {/* Chao + o nhap nhanh */}
      <section className="mb-6 grid gap-6 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <div className="flex items-center gap-3">
            <div className="grid size-11 place-items-center rounded-2xl bg-accent text-accent-fg"><Bot className="size-6" /></div>
            <div><h1 className="text-2xl font-semibold tracking-tight">{greet} 👋</h1><p className="text-sm text-muted">{t('Hôm nay bạn muốn agent giúp gì?')}</p></div>
          </div>
          <form onSubmit={(e) => { e.preventDefault(); if (text.trim()) go(text.trim()) }} className="mt-5 flex items-center gap-2 rounded-2xl border border-line bg-panel p-2 transition focus-within:border-accent">
            <Sparkles className="ml-2 size-4 shrink-0 text-accent" aria-hidden />
            <input value={text} onChange={(e) => setText(e.target.value)} placeholder={t('Nhập yêu cầu rồi nhấn Enter…')} aria-label={t('Yêu cầu')} className="h-10 flex-1 bg-transparent px-2 text-sm placeholder:text-muted/70 focus:outline-none" />
            <button type="submit" disabled={!text.trim()} aria-label={t('Gửi')} className="grid size-9 place-items-center rounded-xl bg-accent text-accent-fg disabled:opacity-40"><ArrowUp className="size-4" /></button>
          </form>
          <div className="mt-3 flex flex-wrap gap-2">
            {suggestions().map((s) => <button key={s} onClick={() => go(s)} className="rounded-full border border-line bg-panel px-3 py-1 text-xs text-muted transition hover:border-accent/60 hover:text-fg">{s}</button>)}
          </div>
        </div>
        <Card className="p-5 lg:col-span-2">
          <div className="flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-sm font-semibold"><ShieldCheck className="size-4 text-accent" />{t('Hoàn tất thiết lập')}</h2>
            <span className="text-xs tabular-nums text-muted">{t('{done}/{total} hoàn thành', { done: doneCount, total: steps.length })}</span>
          </div>
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-panel2" role="progressbar" aria-valuenow={doneCount} aria-valuemax={steps.length}><div className="h-full rounded-full bg-accent transition-all" style={{ width: `${(doneCount / steps.length) * 100}%` }} /></div>
          {doneCount === steps.length ? <p className="mt-4 text-sm text-ok">{t('Bạn đã thiết lập đầy đủ 🎉')}</p> : (
            <ul className="mt-3 space-y-0.5">
              {steps.map((s) => (
                <li key={s.label}>
                  <Link to={s.to} className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-sm transition hover:bg-panel2">
                    {s.done ? <CheckCircle2 className="size-4 shrink-0 text-ok" /> : <Circle className="size-4 shrink-0 text-muted/60" />}
                    <span className={cn('flex-1', s.done && 'text-muted line-through')}>{s.label}</span>
                    {!s.done && <ArrowRight className="size-3.5 text-muted" />}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </section>

      {/* The so lieu */}
      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi icon={MessageSquare} label={t('Lượt gọi model')} value={fmtNum(d.totals.llm_calls)} sub={t('{n} ngày qua', { n: d.days })} chart={<Suspense fallback={null}><Spark data={d.series} k="calls" /></Suspense>} />
        <Kpi icon={Coins} label={t('Token đã dùng')} value={fmtNum(d.totals.prompt_tokens + d.totals.completion_tokens)} sub={d.totals.cost > 0 ? `≈ $${d.totals.cost.toFixed(4)}` : t('{a} vào · {b} ra', { a: fmtNum(d.totals.prompt_tokens), b: fmtNum(d.totals.completion_tokens) })}
          chart={<Suspense fallback={null}><Spark data={d.series} k="prompt" color="var(--info)" /></Suspense>} />
        <Kpi icon={Wrench} label={t('Lần gọi tool')} value={fmtNum(d.totals.tool_calls)} sub={d.totals.tool_errors ? t('{n} lỗi', { n: d.totals.tool_errors }) : t('không có lỗi')} tone={d.totals.tool_errors ? 'var(--warn)' : undefined}
          chart={<Suspense fallback={null}><Spark data={d.series} k="tools" color="var(--ok)" /></Suspense>} />
        <Kpi icon={Gauge} label={t('Độ trễ trung bình')} value={`${(d.totals.avg_latency_ms / 1000).toFixed(1)}s`} sub={d.totals.llm_errors ? t('{n} lỗi', { n: d.totals.llm_errors }) : t('không có lỗi')} tone={d.totals.llm_errors ? 'var(--bad)' : undefined} />
      </section>

      <section className="mt-4 grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader title={t('Hoạt động {n} ngày qua', { n: d.days })} action={<Link to="/dashboard" className="flex items-center gap-1 text-xs text-accent hover:underline">{t('Bảng điều khiển')}<ArrowRight className="size-3" /></Link>} />
          <div className="h-64 p-4">
            {d.totals.llm_calls === 0 ? <p className="grid h-full place-items-center text-sm text-muted">{t('Chưa có dữ liệu. Hãy trò chuyện với agent để bắt đầu.')}</p>
              : <Suspense fallback={<Loading />}><ActivityChart data={d.series} /></Suspense>}
          </div>
        </Card>

        <Card>
          <CardHeader title={t('Trạng thái hệ thống')} />
          <Row tone="ok" label={t('Model mặc định')} value={<span className="flex items-center gap-2"><span className="truncate">{def} · {c.providers[def!]?.model}</span>
            <button onClick={() => { setChecked(true); health.mutate() }} className="shrink-0 text-xs text-accent hover:underline">
              {health.isPending ? t('Đang kiểm tra…') : !checked ? t('Kiểm tra kết nối') : health.data?.ok ? t('Hoạt động · {ms}ms', { ms: health.data.latency_ms ?? 0 }) : t('Không kết nối được')}</button></span>} to="/providers" />
          <Row tone={c.fallback.length ? 'ok' : 'off'} label={t('Provider dự phòng')} value={c.fallback.length ? c.fallback.join(', ') : t('Chưa đặt')} to="/providers" />
          <Row tone={mcpList.length === 0 ? 'off' : mcpOk === mcpList.length ? 'ok' : 'warn'} label={t('MCP server')} value={mcpList.length ? t('{n}/{m} đã kết nối', { n: mcpOk, m: mcpList.length }) : t('Chưa có')} to="/integrations" />
          <Row tone={tg?.running ? 'ok' : tg?.enabled ? 'bad' : 'off'} label="Telegram" value={tg?.running ? t('Đang chạy {bot}', { bot: tg.bot }) : tg?.enabled ? t('Lỗi') : t('Đã tắt')} to="/integrations?tab=channels" />
          <Row tone={hb.data?.enabled ? (hb.data.last_status === 'error' ? 'bad' : 'ok') : 'off'} label="Heartbeat"
            value={hb.data?.enabled ? (hb.data.next_run ? t('Lần tới: {time}', { time: fmtDateTime(hb.data.next_run) }) : t('Đang bật')) : t('Đã tắt')} to="/automations" />
          <Row tone={c.agent.exec_sandbox === 'docker' ? 'ok' : 'warn'} label={t('Sandbox lệnh')} value={c.agent.exec_sandbox === 'docker' ? 'Docker' : t('Tắt (chạy trực tiếp)')} to="/settings?tab=security" />
          <Row tone={c.auth.has_password ? 'ok' : 'warn'} label={t('Mật khẩu giao diện')} value={c.auth.has_password ? t('Đã đặt') : t('Chưa đặt')} to="/settings?tab=security" />
        </Card>
      </section>

      <section className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader title={t('Hội thoại gần đây')} action={<Link to="/chat" className="flex items-center gap-1 text-xs text-accent hover:underline">{t('Xem tất cả')}<ArrowRight className="size-3" /></Link>} />
          {d.recent_sessions.length === 0 ? <p className="p-5 text-sm text-muted">{t('Chưa có hội thoại nào.')}</p> : d.recent_sessions.slice(0, 5).map((s) => (
            <Link key={s.id} to={`/chat?session=${s.id}`} className="flex items-center justify-between gap-3 border-b border-line px-5 py-2.5 text-sm transition last:border-b-0 hover:bg-panel2">
              <span className="flex min-w-0 items-center gap-2"><span className="text-muted">{s.source === 'telegram' ? <Send className="size-3.5" /> : s.source === 'cron' ? <Clock className="size-3.5" /> : s.source === 'heartbeat' ? <HeartPulse className="size-3.5" /> : <MessageSquare className="size-3.5" />}</span><span className="truncate">{s.title}</span></span>
              <span className="shrink-0 text-xs text-muted">{timeAgo(s.updated)}</span>
            </Link>
          ))}
        </Card>

        <Card>
          <CardHeader title={t('Hoạt động gần đây của agent')} action={<Link to="/audit" className="flex items-center gap-1 text-xs text-accent hover:underline">{t('Nhật ký hoạt động')}<ArrowRight className="size-3" /></Link>} />
          {!audit.data?.items.length ? <p className="p-5 text-sm text-muted">{t('Chưa có hoạt động.')}</p> : audit.data.items.map((a) => (
            <div key={a.id} className="flex items-center gap-2 border-b border-line px-5 py-2.5 text-sm last:border-b-0">
              <Activity className="size-3.5 shrink-0 text-muted" /><span className="font-mono text-[13px]">{a.tool}</span>
              <span className="min-w-0 flex-1 truncate font-mono text-xs text-muted">{a.args}</span>
              {a.decision !== 'auto' && <Badge tone={decisionTone[a.decision as keyof typeof decisionTone] ?? 'neutral'}>{a.decision === 'approved' ? t('Cho phép') : t('Từ chối')}</Badge>}
              <span className="shrink-0 text-xs text-muted">{timeAgo(a.ts)}</span>
            </div>
          ))}
        </Card>

        <Card>
          <CardHeader title={t('Thông báo mới')} action={<Link to="/notifications" className="flex items-center gap-1 text-xs text-accent hover:underline">{t('Hộp thư')}{(inbox.data?.unread ?? 0) > 0 && <Badge tone="accent">{inbox.data?.unread}</Badge>}</Link>} />
          {!inbox.data?.items.length ? <p className="p-5 text-sm text-muted">{t('Không có thông báo.')}</p> : inbox.data.items.slice(0, 4).map((n) => (
            <Link key={n.id} to="/notifications" className="block border-b border-line px-5 py-2.5 transition last:border-b-0 hover:bg-panel2">
              <p className="flex items-center gap-2 text-sm"><Bell className={cn('size-3.5', n.read ? 'text-muted' : 'text-accent')} /><span className="truncate font-medium">{n.title}</span><span className="ml-auto shrink-0 text-xs text-muted">{timeAgo(n.ts)}</span></p>
              <p className="mt-0.5 line-clamp-1 pl-5 text-xs text-muted">{n.body}</p>
            </Link>
          ))}
        </Card>

        <div className="grid gap-4">
          <Card className="p-5">
            <div className="flex items-center justify-between"><h3 className="flex items-center gap-2 text-sm font-semibold"><Puzzle className="size-4 text-muted" />{t('Kỹ năng')}</h3><Link to="/skills" className="text-xs text-accent hover:underline">{t('Quản lý kỹ năng')}</Link></div>
            <p className="mt-2 text-2xl font-semibold tabular-nums">{d.skills.active}<span className="text-sm font-normal text-muted"> {t('đang hoạt động')}</span></p>
            {d.skills.needs_setup > 0 && <p className="text-xs text-warn">{t('{n} cần thiết lập', { n: d.skills.needs_setup })}</p>}
          </Card>
          <Card className="p-5">
            <div className="flex items-center justify-between"><h3 className="flex items-center gap-2 text-sm font-semibold"><Clock className="size-4 text-muted" />{t('Lịch sắp tới')}</h3><Link to="/automations" className="text-xs text-accent hover:underline">{t('Tự động hóa')}</Link></div>
            {next.length === 0 ? <p className="mt-2 text-sm text-muted">{t('Chưa có automation nào.')}</p> : (
              <ul className="mt-2 space-y-1.5">{next.map((j) => <li key={j.id} className="flex items-center justify-between gap-2 text-sm"><span className="truncate">{j.name}</span><span className="shrink-0 text-xs text-muted">{fmtDateTime(j.next_run)}</span></li>)}</ul>
            )}
          </Card>
          <Card className="p-5">
            <h3 className="flex items-center gap-2 text-sm font-semibold"><Plug className="size-4 text-muted" />{t('Tool dùng nhiều nhất')}</h3>
            {d.top_tools.length === 0 ? <p className="mt-2 text-sm text-muted">{t('Chưa có dữ liệu.')}</p> : (
              <ul className="mt-2 space-y-1.5">{d.top_tools.slice(0, 4).map((x) => (
                <li key={x.name} className="text-sm"><div className="flex justify-between"><span className="font-mono text-[13px]">{x.name}</span><span className="tabular-nums text-muted">{x.n}</span></div>
                  <div className="mt-1 h-1 overflow-hidden rounded-full bg-panel2"><div className="h-full rounded-full bg-accent/70" style={{ width: `${(x.n / d.top_tools[0].n) * 100}%` }} /></div></li>
              ))}</ul>
            )}
          </Card>
        </div>
      </section>
    </Page>
  )
}
