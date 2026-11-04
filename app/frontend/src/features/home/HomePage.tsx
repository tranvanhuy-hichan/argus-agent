import { lazy, Suspense, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { ArrowRight, ArrowUp, Bell, Circle, Clock, FolderCog, HeartPulse, ListTodo, MessageSquare, Plug, Puzzle, Send, Sparkles, type LucideIcon } from 'lucide-react'
import { AgentMark } from '@/components/ui/AgentMark'
import { Loading, Page } from '@/components/ui/misc'
import { api } from '@/lib/api'
import { t, tk } from '@/lib/i18n.ts'
import { useConfig, useDashboard, useHeartbeat, useJobs, useMcp, useSkills } from '@/lib/queries'
import type { NotificationItem, TelegramStatus } from '@/lib/types'
import { cn, fmtDateTime, fmtNum, timeAgo } from '@/lib/utils'
import { HabitSuggestions } from './HabitSuggestions'

const Spark = lazy(() => import('./HomeCharts').then((m) => ({ default: m.Spark })))

const QUICK: { to: string; icon: LucideIcon; label: string }[] = [
  { to: '/tasks', icon: ListTodo, label: tk('Giao việc dài') },
  { to: '/automations', icon: Clock, label: tk('Tự động hóa mới') },
  { to: '/skills?tab=discover', icon: Puzzle, label: tk('Cài kỹ năng') },
  { to: '/integrations?tab=channels', icon: Send, label: tk('Nối Telegram') },
  { to: '/providers', icon: Plug, label: tk('Thêm model') },
  { to: '/workspace', icon: FolderCog, label: tk('Mở workspace') },
]

/** Tiêu đề một vùng nội dung: chữ + liên kết, không hộp bao quanh. */
function Block({ title, to, cta, children }: { title: string; to?: string; cta?: string; children: React.ReactNode }) {
  return (
    <section>
      <div className="mb-1 flex items-baseline justify-between">
        <h2 className="text-[13px] font-semibold uppercase tracking-wide text-muted">{title}</h2>
        {to && <Link to={to} className="flex items-center gap-1 text-xs text-accent hover:underline">{cta}<ArrowRight className="size-3" /></Link>}
      </div>
      <div className="divide-y divide-line/70">{children}</div>
    </section>
  )
}

const rowCls = 'flex items-center justify-between gap-3 py-2.5 text-sm'
const Muted = ({ children }: { children: React.ReactNode }) => <p className="py-3 text-sm text-muted">{children}</p>

const Dot = ({ tone }: { tone: 'ok' | 'warn' | 'bad' | 'off' }) => (
  <span className={cn('inline-block size-2 shrink-0 rounded-full', tone === 'ok' && 'bg-ok', tone === 'warn' && 'bg-warn', tone === 'bad' && 'bg-bad', tone === 'off' && 'bg-muted/50')} aria-hidden />
)

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
  const cloud = Object.values(c.providers).some((p) => p.type === 'anthropic' || p.type === 'cli' || !/localhost|127\.0\.0\.1/.test(p.base_url))
  const steps: { done: boolean; label: string; to: string }[] = [
    { done: cloud, label: t('Thêm một model mạnh hơn (cloud)'), to: '/providers' },
    { done: (skills.data ?? []).some((s) => s.origin), label: t('Cài một skill từ ClawHub'), to: '/skills?tab=discover' },
    { done: !!tg?.running, label: t('Kết nối Telegram để nhắn từ điện thoại'), to: '/integrations?tab=channels' },
    { done: c.heartbeat.enabled, label: t('Bật heartbeat để agent chủ động báo tin'), to: '/automations' },
    { done: c.auth.has_password, label: t('Đặt mật khẩu cho giao diện'), to: '/settings?tab=security' },
    { done: mcpList.length > 0, label: t('Nối một MCP server của bạn'), to: '/integrations' },
    { done: c.agent.exec_sandbox === 'docker', label: t('Bật sandbox Docker cho lệnh shell'), to: '/settings?tab=security' },
  ]
  const todo = steps.filter((x) => !x.done)
  const next = jobs.data?.filter((j) => j.enabled && j.next_run).sort((a, b) => (a.next_run ?? 0) - (b.next_run ?? 0)).slice(0, 3) ?? []
  const sourceIcon = (src: string) => src === 'telegram' ? Send : src === 'cron' ? Clock : src === 'heartbeat' ? HeartPulse : MessageSquare
  // Chỉ nêu những gì cần chú ý; mọi thứ bình thường thì không chiếm chỗ.
  const alerts: { tone: 'warn' | 'bad'; text: string; to: string }[] = [
    ...(mcpList.length && mcpOk < mcpList.length ? [{ tone: 'warn' as const, text: t('MCP server: {n}/{m} đã kết nối', { n: mcpOk, m: mcpList.length }), to: '/integrations' }] : []),
    ...(tg?.enabled && !tg.running ? [{ tone: 'bad' as const, text: t('Telegram đang lỗi'), to: '/integrations?tab=channels' }] : []),
    ...(hb.data?.enabled && hb.data.last_status === 'error' ? [{ tone: 'bad' as const, text: t('Heartbeat đang lỗi'), to: '/automations' }] : []),
    ...(d.totals.llm_errors ? [{ tone: 'warn' as const, text: t('{n} lỗi gọi model', { n: d.totals.llm_errors }), to: '/activity' }] : []),
  ]

  return (
    <Page>
      <div className="grid gap-x-10 gap-y-8 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="min-w-0 space-y-8">
          <header className="flex items-center gap-4">
            <AgentMark />
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">{greet}</h1>
              <p className="text-sm text-muted">{t('Hôm nay bạn muốn agent giúp gì?')}</p>
            </div>
          </header>

          <div>
            <form onSubmit={(e) => { e.preventDefault(); if (text.trim()) go(text.trim()) }} className="flex items-center gap-2 rounded-2xl border border-line bg-panel p-2 transition focus-within:border-accent">
              <Sparkles className="ml-3 size-5 shrink-0 text-accent" aria-hidden />
              <input value={text} onChange={(e) => setText(e.target.value)} placeholder={t('Nhập yêu cầu rồi nhấn Enter…')} aria-label={t('Yêu cầu')} className="h-12 flex-1 bg-transparent px-2 text-[15px] placeholder:text-muted/70 focus:outline-none" />
              <button type="submit" disabled={!text.trim()} aria-label={t('Gửi')} className="grid size-11 place-items-center rounded-xl bg-accent text-accent-fg transition hover:brightness-110 disabled:opacity-40"><ArrowUp className="size-5" /></button>
            </form>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              {suggestions().map((x) => <button key={x} onClick={() => go(x)} className="rounded-full border border-line px-3 py-1 text-[13px] text-muted transition hover:border-accent/60 hover:text-fg">{x}</button>)}
            </div>
            <p className="mt-3 flex items-center gap-1.5 text-xs text-muted">
              <Dot tone="ok" />{t('Đang dùng {name}', { name: `${def} · ${c.providers[def!]?.model}` })}
              <button onClick={() => { setChecked(true); health.mutate() }} className="ml-1 text-accent hover:underline">
                {health.isPending ? t('Đang kiểm tra…') : !checked ? t('Kiểm tra kết nối') : health.data?.ok ? t('Hoạt động · {ms}ms', { ms: health.data.latency_ms ?? 0 }) : t('Không kết nối được')}
              </button>
            </p>
          </div>

          <HabitSuggestions />

          {alerts.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {alerts.map((a) => (
                <Link key={a.text} to={a.to} className="flex items-center gap-2 rounded-lg border border-line px-3 py-1.5 text-sm transition hover:bg-panel"><Dot tone={a.tone} />{a.text}</Link>
              ))}
            </div>
          )}

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 2xl:grid-cols-6">
            {QUICK.map(({ to, icon: Icon, label }) => (
              <Link key={to} to={to} className="flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm text-muted transition hover:bg-panel hover:text-fg">
                <Icon className="size-[18px] shrink-0 text-accent" /><span className="truncate">{t(label)}</span>
              </Link>
            ))}
          </div>

          <Block title={t('Hội thoại gần đây')} to="/chat" cta={t('Xem tất cả')}>
            {d.recent_sessions.length === 0 ? <Muted>{t('Chưa có hội thoại nào.')}</Muted> : d.recent_sessions.slice(0, 7).map((s) => {
              const Icon = sourceIcon(s.source)
              return (
                <Link key={s.id} to={`/chat?session=${s.id}`} className={cn(rowCls, 'transition hover:text-accent')}>
                  <span className="flex min-w-0 items-center gap-3"><Icon className="size-4 shrink-0 text-muted" /><span className="truncate">{s.title}</span></span>
                  <span className="shrink-0 text-xs text-muted">{timeAgo(s.updated)}</span>
                </Link>
              )
            })}
          </Block>

          <Block title={t('Tuần qua của bạn')} to="/activity" cta={t('Thống kê chi tiết')}>
            <div className="py-4">
              <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                {[
                  [t('Cuộc trò chuyện'), fmtNum(d.totals.sessions)],
                  [t('Tin nhắn trao đổi'), fmtNum(d.totals.messages)],
                  [t('Việc agent đã làm'), fmtNum(d.totals.tool_calls)],
                  [t('Kỹ năng đang dùng'), fmtNum(d.skills.active)],
                ].map(([k, v]) => (
                  <div key={k}><dd className="text-3xl font-semibold tabular-nums">{v}</dd><dt className="mt-0.5 text-xs text-muted">{k}</dt></div>
                ))}
              </dl>
              <div className="mt-4 h-24"><Suspense fallback={null}><Spark data={d.series} k="calls" /></Suspense></div>
              <p className="mt-1 text-xs text-muted">{t('Số lần bạn nhờ agent mỗi ngày trong {n} ngày qua', { n: d.days })}</p>
            </div>
          </Block>
        </div>

        <aside className="min-w-0 space-y-8 xl:border-l xl:border-line xl:pl-8">
          {todo.length > 0 && (
            <Block title={t('Hoàn tất thiết lập')}>
              <div className="pb-3">
                <div className="mb-1.5 flex justify-between text-xs text-muted"><span>{t('{done}/{total} hoàn thành', { done: steps.length - todo.length, total: steps.length })}</span></div>
                <div className="h-1.5 overflow-hidden rounded-full bg-panel2" role="progressbar" aria-valuenow={steps.length - todo.length} aria-valuemax={steps.length} aria-label={t('Hoàn tất thiết lập')}>
                  <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${((steps.length - todo.length) / steps.length) * 100}%` }} />
                </div>
              </div>
              {todo.slice(0, 3).map((x) => (
                <Link key={x.label} to={x.to} className={cn(rowCls, 'transition hover:text-accent')}>
                  <span className="flex items-center gap-2.5"><Circle className="size-4 shrink-0 text-muted/60" />{x.label}</span><ArrowRight className="size-3.5 shrink-0 text-muted" />
                </Link>
              ))}
            </Block>
          )}

          <Block title={t('Lịch sắp tới')} to="/automations" cta={t('Tự động hóa')}>
            {next.length === 0 ? <Muted>{t('Chưa có automation nào.')}</Muted> : next.map((j) => (
              <div key={j.id} className={rowCls}><span className="truncate">{j.name}</span><span className="shrink-0 text-xs text-muted">{fmtDateTime(j.next_run)}</span></div>
            ))}
          </Block>

          <Block title={t('Thông báo mới')} to="/notifications" cta={(inbox.data?.unread ?? 0) > 0 ? `${t('Hộp thư')} · ${inbox.data?.unread}` : t('Hộp thư')}>
            {!inbox.data?.items.length ? <Muted>{t('Không có thông báo.')}</Muted> : inbox.data.items.slice(0, 4).map((n) => (
              <Link key={n.id} to="/notifications" className="block py-2.5 transition hover:text-accent">
                <p className="flex items-center gap-2 text-sm"><Bell className={cn('size-3.5 shrink-0', n.read ? 'text-muted' : 'text-accent')} /><span className="truncate font-medium">{n.title}</span><span className="ml-auto shrink-0 text-xs text-muted">{timeAgo(n.ts)}</span></p>
                <p className="mt-0.5 line-clamp-1 pl-5 text-xs text-muted">{n.body}</p>
              </Link>
            ))}
          </Block>
        </aside>
      </div>
    </Page>
  )
}
