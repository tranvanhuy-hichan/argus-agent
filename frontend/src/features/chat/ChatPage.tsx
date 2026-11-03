import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowUp, Bot, MessageSquarePlus, Square, Trash2 } from 'lucide-react'
import { Select } from '@/components/ui/Form'
import { Loading } from '@/components/ui/misc'
import { api } from '@/lib/api'
import { useConfig, useSessions } from '@/lib/queries'
import { cn, timeAgo } from '@/lib/utils'
import { MessageView } from './MessageView'
import { useChat } from './useChat'

const SUGGESTIONS = ['Bạn làm được những gì?', 'Tạo file ghi-chu.md trong workspace với 3 ý tưởng dự án', 'Liệt kê các skill bạn đang có', 'Chạy lệnh df -h và tóm tắt dung lượng đĩa']

export function ChatPage() {
  const chat = useChat()
  const cfg = useConfig()
  const sessions = useSessions()
  const qc = useQueryClient()
  const nav = useNavigate()
  const location = useLocation()
  const [text, setText] = useState('')
  const [provider, setProvider] = useState<string | null>(null)
  const scroller = useRef<HTMLDivElement>(null)
  const stick = useRef(true)
  const del = useMutation({ mutationFn: (id: string) => api.del(`/api/sessions/${id}`), onSuccess: () => qc.invalidateQueries({ queryKey: ['sessions'] }) })

  // Cau hoi chuyen tu Trang chu qua router state
  const initial = (location.state as { prompt?: string } | null)?.prompt
  const sentInitial = useRef(false)
  useEffect(() => {
    if (initial && !sentInitial.current && cfg.data) {
      sentInitial.current = true
      nav('.', { replace: true, state: null })
      void chat.send(initial, null)
    }
  }, [initial, cfg.data, chat, nav])

  useEffect(() => {
    const el = scroller.current
    if (el && stick.current) el.scrollTop = el.scrollHeight
  }, [chat.items])

  if (!cfg.data) return <Loading />
  const providers = Object.keys(cfg.data.config.providers)
  const active = provider ?? cfg.data.config.default_provider
  const submit = () => {
    if (!text.trim() || chat.busy) return
    stick.current = true
    void chat.send(text, active)
    setText('')
  }
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit() }
  }

  return (
    <div className="flex h-full">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-line bg-panel lg:flex">
        <div className="p-3">
          <button onClick={chat.reset} className="flex h-9 w-full items-center gap-2 rounded-lg border border-line px-3 text-sm font-medium transition hover:border-accent hover:text-accent">
            <MessageSquarePlus className="size-4" />Hội thoại mới
          </button>
        </div>
        <div className="flex-1 space-y-0.5 overflow-y-auto px-2 pb-3">
          {sessions.data?.map((s) => (
            <div key={s.id} className={cn('group flex items-center gap-1 rounded-lg px-2.5 py-2 transition hover:bg-panel2', s.id === chat.sessionId && 'bg-panel2')}>
              <button onClick={() => void chat.open(s.id)} className="min-w-0 flex-1 text-left">
                <p className="truncate text-sm">{s.title}</p>
                <p className="text-[11px] text-muted">{s.source === 'cron' ? 'Automation · ' : ''}{timeAgo(s.updated)}</p>
              </button>
              <button
                aria-label="Xóa hội thoại"
                onClick={() => { del.mutate(s.id); if (s.id === chat.sessionId) chat.reset() }}
                className="rounded p-1 text-muted opacity-0 transition hover:text-bad focus:opacity-100 group-hover:opacity-100"
              ><Trash2 className="size-3.5" /></button>
            </div>
          ))}
          {sessions.data?.length === 0 && <p className="px-3 py-6 text-center text-xs text-muted">Chưa có hội thoại nào</p>}
        </div>
      </aside>

      <section className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-line px-5">
          <h1 className="text-sm font-semibold">Chat</h1>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted">Model</span>
            <Select value={active} onChange={(e) => setProvider(e.target.value)} className="h-8 w-auto text-xs" aria-label="Chọn provider">
              {providers.map((p) => <option key={p} value={p}>{p} · {cfg.data.config.providers[p].model}</option>)}
            </Select>
          </div>
        </header>

        <div ref={scroller} onScroll={(e) => { const el = e.currentTarget; stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80 }} className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-5xl space-y-4 px-5 py-6">
            {chat.items.length === 0 ? (
              <div className="flex flex-col items-center pt-[12vh] text-center">
                <div className="mb-4 grid size-14 place-items-center rounded-2xl bg-accent text-accent-fg"><Bot className="size-7" /></div>
                <h2 className="text-xl font-semibold">Mình có thể giúp gì cho bạn?</h2>
                <p className="mt-1 text-sm text-muted">Agent có thể đọc/ghi file, chạy lệnh, gọi API và dùng skill đã cài.</p>
                <div className="mt-6 grid w-full max-w-xl gap-2 sm:grid-cols-2">
                  {SUGGESTIONS.map((s) => (
                    <button key={s} onClick={() => { stick.current = true; void chat.send(s, active) }} className="rounded-xl border border-line bg-panel px-3.5 py-3 text-left text-sm text-muted transition hover:border-accent/60 hover:text-fg">{s}</button>
                  ))}
                </div>
              </div>
            ) : (
              chat.items.map((it) => <MessageView key={it.key} item={it} onDecide={(aid, ok) => void chat.decide(aid, ok)} />)
            )}
          </div>
        </div>

        <div className="shrink-0 border-t border-line bg-bg px-5 py-4">
          <div className="mx-auto flex max-w-5xl items-end gap-2 rounded-2xl border border-line bg-panel p-2 transition focus-within:border-accent">
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={onKey}
              rows={1}
              placeholder="Nhắn tin cho agent…  (Enter để gửi, Shift+Enter xuống dòng)"
              aria-label="Tin nhắn"
              className="max-h-48 min-h-9 flex-1 resize-none bg-transparent px-2.5 py-1.5 text-sm placeholder:text-muted/70 focus:outline-none focus-visible:outline-none"
              style={{ height: 'auto', fieldSizing: 'content' } as React.CSSProperties}
            />
            {chat.busy ? (
              <button onClick={chat.stop} aria-label="Dừng" className="grid size-9 shrink-0 place-items-center rounded-xl bg-panel2 transition hover:bg-line"><Square className="size-3.5 fill-current" /></button>
            ) : (
              <button onClick={submit} disabled={!text.trim()} aria-label="Gửi" className="grid size-9 shrink-0 place-items-center rounded-xl bg-accent text-accent-fg transition hover:brightness-110 disabled:opacity-40"><ArrowUp className="size-4" /></button>
            )}
          </div>
        </div>
      </section>
    </div>
  )
}
