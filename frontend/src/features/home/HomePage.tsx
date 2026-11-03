import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, ArrowUp, Bot, CircleCheck, CircleX, Clock, Plug, Puzzle } from 'lucide-react'
import { useMutation } from '@tanstack/react-query'
import { Card } from '@/components/ui/Card'
import { Loading, Page } from '@/components/ui/misc'
import { api } from '@/lib/api'
import { useConfig, useDashboard } from '@/lib/queries'
import { timeAgo } from '@/lib/utils'

export function HomePage() {
  const nav = useNavigate()
  const cfg = useConfig()
  const dash = useDashboard(7)
  const [text, setText] = useState('')
  const def = cfg.data?.config.default_provider
  const health = useMutation({ mutationFn: () => api.post<{ ok: boolean; latency_ms?: number }>(`/api/providers/${def}/test`, {}) })
  const [checked, setChecked] = useState(false)

  if (!cfg.data || !dash.data) return <Loading />
  const d = dash.data
  const go = (prompt?: string) => nav('/chat', { state: prompt ? { prompt } : null })
  const hr = new Date().getHours()
  const greet = hr < 11 ? 'Chào buổi sáng' : hr < 18 ? 'Chào buổi chiều' : 'Chào buổi tối'

  return (
    <Page>
      <div className="flex flex-col items-center pb-8 pt-6 text-center">
        <div className="mb-4 grid size-14 place-items-center rounded-2xl bg-accent text-accent-fg"><Bot className="size-7" /></div>
        <h1 className="text-3xl font-semibold tracking-tight">{greet} 👋</h1>
        <p className="mt-2 text-muted">Bạn muốn agent giúp gì hôm nay?</p>
        <form onSubmit={(e) => { e.preventDefault(); if (text.trim()) go(text.trim()) }} className="mt-6 flex w-full items-center gap-2 rounded-2xl border border-line bg-panel p-2 transition focus-within:border-accent">
          <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Nhập yêu cầu rồi nhấn Enter…" aria-label="Yêu cầu" className="h-9 flex-1 bg-transparent px-3 text-sm placeholder:text-muted/70 focus:outline-none" />
          <button type="submit" disabled={!text.trim()} aria-label="Gửi" className="grid size-9 place-items-center rounded-xl bg-accent text-accent-fg disabled:opacity-40"><ArrowUp className="size-4" /></button>
        </form>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <Card className="p-4">
          <div className="flex items-center gap-2 text-xs font-medium text-muted"><Plug className="size-3.5" />Model đang dùng</div>
          <p className="mt-2 font-semibold">{def}</p>
          <p className="truncate text-xs text-muted">{cfg.data.config.providers[def!]?.model}</p>
          <button onClick={() => { setChecked(true); health.mutate() }} className="mt-2 flex items-center gap-1.5 text-xs">
            {health.isPending ? <span className="text-muted">Đang kiểm tra…</span> : !checked ? <span className="text-accent hover:underline">Kiểm tra kết nối</span> : health.data?.ok ? <span className="flex items-center gap-1 text-ok"><CircleCheck className="size-3.5" />Hoạt động · {health.data.latency_ms}ms</span> : <span className="flex items-center gap-1 text-bad"><CircleX className="size-3.5" />Không kết nối được</span>}
          </button>
        </Card>
        <Link to="/skills"><Card className="h-full p-4 transition hover:border-accent/50">
          <div className="flex items-center gap-2 text-xs font-medium text-muted"><Puzzle className="size-3.5" />Skills</div>
          <p className="mt-2 text-2xl font-semibold tabular-nums">{d.skills.active}<span className="text-sm font-normal text-muted"> đang hoạt động</span></p>
          <p className={`text-xs ${d.skills.needs_setup ? 'text-warn' : 'text-muted'}`}>{d.skills.needs_setup ? `${d.skills.needs_setup} cần thiết lập` : `${d.skills.total} đã cài`}</p>
        </Card></Link>
        <Link to="/automations"><Card className="h-full p-4 transition hover:border-accent/50">
          <div className="flex items-center gap-2 text-xs font-medium text-muted"><Clock className="size-3.5" />Automations</div>
          <p className="mt-2 text-2xl font-semibold tabular-nums">{d.automations.enabled}<span className="text-sm font-normal text-muted"> đang bật</span></p>
          <p className="text-xs text-muted">{d.automations.total} tổng cộng</p>
        </Card></Link>
      </div>

      <div className="mt-8">
        <div className="mb-2 flex items-center justify-between"><h2 className="text-sm font-semibold">Hội thoại gần đây</h2><Link to="/chat" className="flex items-center gap-1 text-xs text-accent hover:underline">Xem tất cả<ArrowRight className="size-3" /></Link></div>
        <Card>
          {d.recent_sessions.length === 0 ? <p className="p-6 text-center text-sm text-muted">Chưa có hội thoại nào.</p> : d.recent_sessions.map((s) => (
            <Link key={s.id} to="/chat" className="flex items-center justify-between gap-3 border-b border-line px-4 py-3 text-sm transition last:border-b-0 hover:bg-panel2"><span className="truncate">{s.title}</span><span className="shrink-0 text-xs text-muted">{timeAgo(s.updated)}</span></Link>
          ))}
        </Card>
      </div>
    </Page>
  )
}
