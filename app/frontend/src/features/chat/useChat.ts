import { useCallback, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { attachChat, streamChat, type ChatEvent, type RunState } from '@/lib/chatStream'
import type { PlanItem, WireMessage } from '@/lib/types'
import { t } from '@/lib/i18n.ts'
import { errMsg } from '@/lib/utils'

export type ToolItem = { key: string; kind: 'tool'; callId: string; name: string; args: Record<string, unknown>; risk?: string; result?: string; ok?: boolean; duration?: number; decision?: string }
export type Item =
  | { key: string; kind: 'user'; text: string; attachments?: string[] }
  | { key: string; kind: 'assistant'; text: string; provider?: string; streaming?: boolean; duration?: number }
  | { key: string; kind: 'thinking'; text: string; streaming: boolean; provider?: string }
  | ToolItem
  | { key: string; kind: 'approval'; aid: string; approvalKind: string; detail: string; status: 'pending' | 'allowed' | 'denied' }
  | { key: string; kind: 'question'; qid: string; question: string; options: string[]; answer: string | null }
  | { key: string; kind: 'summary'; files: { path: string; status: string; added: number; removed: number }[]; undone: boolean }
  | { key: string; kind: 'notice' | 'error'; text: string }

let seq = 0
const k = () => `i${++seq}`

export function fromWire(msgs: WireMessage[]): Item[] {
  const results = new Map(msgs.filter((m) => m.role === 'tool').map((m) => [m.tool_call_id, m.content]))
  const out: Item[] = []
  for (const m of msgs) {
    if (m.role === 'user') out.push({ key: k(), kind: 'user', text: m.content, attachments: m.attachments })
    else if (m.role === 'assistant') {
      if (m.content) out.push({ key: k(), kind: 'assistant', text: m.content })
      for (const c of m.tool_calls ?? []) out.push({ key: k(), kind: 'tool', callId: c.id, name: c.name, args: c.args, result: results.get(c.id) ?? '', ok: true })
    }
  }
  return out
}

export function useChat() {
  const qc = useQueryClient()
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [items, setItems] = useState<Item[]>([])
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState<string | null>(null)
  const [filesTick, setFilesTick] = useState(0)
  const [plan, setPlan] = useState<PlanItem[]>([])
  const abort = useRef<AbortController | null>(null)
  const sessionRef = useRef<string | null>(null)
  const currentProviderRef = useRef<string | null>(null)
  sessionRef.current = sessionId

  const apply = useCallback((e: ChatEvent) => {
    if (e.type === 'status') {
      if (e.vars?.name) currentProviderRef.current = String(e.vars.name)
      return setStatus(e.tpl ? t(e.tpl, e.vars) : e.text)
    }
    if (e.type === 'files') return setFilesTick((n) => n + 1)
    if (e.type === 'plan') return setPlan(e.items)
    if (e.type === 'session') { setSessionId(e.id); sessionRef.current = e.id; return }
    setItems((prev) => {
      // thinking dang mo thi dong lai khi co su kien khac
      const base = e.type === 'thinking' ? prev : prev.map((it) => (it.kind === 'thinking' && it.streaming ? { ...it, streaming: false } : it))
      const last = base[base.length - 1]
      switch (e.type) {
        case 'thinking':
          setStatus(null)
          if (last?.kind === 'thinking' && last.streaming) return [...base.slice(0, -1), { ...last, text: last.text + e.text }]
          return [...base, { key: k(), kind: 'thinking', text: e.text, streaming: true, provider: currentProviderRef.current || undefined }]
        case 'delta': {
          setStatus(null)
          let txt = e.text
          if (txt.includes('<think>') || txt.includes('</think>')) {
            txt = txt.replace(/<\/?think>/g, '')
          }
          if (!txt) return base
          if (last?.kind === 'assistant' && last.streaming) return [...base.slice(0, -1), { ...last, text: last.text + txt }]
          return [...base, { key: k(), kind: 'assistant', text: txt, streaming: true }]
        }
        case 'assistant': {
          const done = { kind: 'assistant' as const, text: e.content, provider: e.provider, streaming: false, duration: e.duration_ms }
          if (last?.kind === 'assistant' && last.streaming) return [...base.slice(0, -1), { ...last, ...done }]
          return e.content ? [...base, { key: k(), ...done }] : base
        }
        case 'tool':
          return [...base, { key: k(), kind: 'tool', callId: e.id, name: e.name, args: e.args, risk: e.risk }]
        case 'tool_result':
          return base.map((it) => (it.kind === 'tool' && it.callId === e.id ? { ...it, result: e.result, ok: e.ok, duration: e.duration_ms, decision: e.decision } : it))
        case 'approval':
          return [...base, { key: k(), kind: 'approval', aid: e.id, approvalKind: e.kind, detail: e.detail, status: 'pending' }]
        case 'question':
          return [...base, { key: k(), kind: 'question', qid: e.id, question: e.question, options: e.options, answer: null }]
        case 'question_done':
          return base.map((it) => (it.kind === 'question' && it.qid === e.id && it.answer === null ? { ...it, answer: e.answer || '—' } : it))
        case 'turn_summary':
          return [...base.filter((it) => it.kind !== 'summary'), { key: k(), kind: 'summary', files: e.files, undone: false }]
        case 'approval_done':
          return base.map((it) => (it.kind === 'approval' && it.aid === e.id && it.status === 'pending' ? { ...it, status: e.ok ? 'allowed' : 'denied' } : it))
        case 'notice':
          return [...base, { key: k(), kind: 'notice', text: e.tpl ? t(e.tpl, e.vars) : e.message }]
        case 'error':
          return [...base, { key: k(), kind: 'error', text: e.tpl ? t(e.tpl, e.vars) : e.message }]
        default:
          return base
      }
    })
  }, [])

  const ensureSession = useCallback(async () => {
    if (sessionRef.current) return sessionRef.current
    const r = await api.post<{ id: string }>('/api/sessions', {})
    setSessionId(r.id)
    sessionRef.current = r.id
    void qc.invalidateQueries({ queryKey: ['sessions'] })
    return r.id
  }, [qc])

  const send = useCallback(async (text: string, provider: string | null, attachments: string[] = [], opts: { permission?: string; effort?: string; docs?: boolean; temperature?: number; max_tokens?: number } = {}) => {
    if (busy || !text.trim()) return
    currentProviderRef.current = provider
    setBusy(true)
    setStatus(t('Đang gửi…'))
    setItems((p) => [...p, { key: k(), kind: 'user', text, attachments }])
    const ctl = new AbortController()
    abort.current = ctl
    try {
      await streamChat({ text, session: sessionRef.current, provider, attachments, ...opts }, apply, ctl.signal)
    } catch (e) {
      if (!ctl.signal.aborted) apply({ type: 'error', message: errMsg(e) })
    } finally {
      if (abort.current === ctl) { // da doi sang phien khac thi khong dong vao trang thai cua phien moi
        setItems((p) => p.map((it) => ((it.kind === 'assistant' || it.kind === 'thinking') && it.streaming ? { ...it, streaming: false } : it)))
        setBusy(false)
        setStatus(null)
      }
      setFilesTick((n) => n + 1)
      void qc.invalidateQueries({ queryKey: ['sessions'] })
      void qc.invalidateQueries({ queryKey: ['dashboard'] })
    }
  }, [apply, busy, qc])

  const stop = useCallback(() => {
    const sid = sessionRef.current
    const ctl = abort.current
    if (!sid) return ctl?.abort()
    setStatus(t('Đang dừng…'))
    // bao server dung that; cho no gui 'done' roi stream tu ket thuc. Neu server khong phan hoi thi moi ngat o giao dien.
    void api.post(`/api/sessions/${sid}/stop`, {}).catch(() => ctl?.abort())
    setTimeout(() => ctl?.abort(), 4000)
  }, [])

  /** Gan luong cua luot dang chay tren server vao giao dien (idempotent: huy luong cu truoc). */
  const follow = useCallback(async (sid: string, st: RunState) => {
    abort.current?.abort()
    const ctl = new AbortController()
    abort.current = ctl
    setBusy(true)
    setStatus(t('Đang xử lý…'))
    setItems((p) => [...p.filter((it) => it.kind !== 'approval' && it.kind !== 'question'), ...(st.questions ?? []).map((q) => ({ key: k(), kind: 'question' as const, qid: q.id, question: q.question, options: q.options, answer: null })), ...st.pending.map((a) => ({ key: k(), kind: 'approval' as const, aid: a.id, approvalKind: a.kind, detail: a.detail, status: 'pending' as const }))])
    try {
      await attachChat(sid, st.cursor, apply, ctl.signal)
    } catch (e) {
      if (!ctl.signal.aborted) apply({ type: 'error', message: errMsg(e) })
    } finally {
      if (abort.current === ctl) {
        setItems((p) => p.map((it) => ((it.kind === 'assistant' || it.kind === 'thinking') && it.streaming ? { ...it, streaming: false } : it)))
        setBusy(false)
        setStatus(null)
        setFilesTick((n) => n + 1)
        void qc.invalidateQueries({ queryKey: ['sessions'] })
      }
    }
  }, [apply, qc])

  const open = useCallback(async (sid: string) => {
    abort.current?.abort() // chi ngat phia giao dien; agent tren server van chay tiep
    setBusy(false)
    setStatus(null)
    const [s, st] = await Promise.all([
      api.get<{ messages: WireMessage[] }>(`/api/sessions/${sid}`),
      api.get<RunState>(`/api/sessions/${sid}/run`).catch(() => null),
    ])
    setSessionId(sid)
    sessionRef.current = sid
    setItems(fromWire(s.messages))
    if (st?.active) void follow(sid, st)
    api.get<{ items: PlanItem[] }>(`/api/sessions/${sid}/plan`).then((p) => setPlan(p.items)).catch(() => setPlan([]))
  }, [follow])

  const reset = useCallback(() => {
    abort.current?.abort()
    setBusy(false)
    setStatus(null)
    setSessionId(null)
    sessionRef.current = null
    setItems([])
    setPlan([])
  }, [])

  const decide = useCallback(async (aid: string, ok: boolean) => {
    setItems((p) => p.map((it) => (it.kind === 'approval' && it.aid === aid ? { ...it, status: ok ? 'allowed' : 'denied' } : it)))
    await api.post(`/api/approvals/${aid}`, { ok })
  }, [])

  const answer = useCallback(async (qid: string, text: string) => {
    setItems((p) => p.map((it) => (it.kind === 'question' && it.qid === qid ? { ...it, answer: text } : it)))
    await api.post(`/api/questions/${qid}`, { answer: text })
  }, [])

  /** Hoan tac cac file agent da ghi/sua trong luot gan nhat. */
  const undo = useCallback(async () => {
    const sid = sessionRef.current
    if (!sid) return
    await api.post(`/api/sessions/${sid}/undo`, {})
    setItems((p) => p.map((it) => (it.kind === 'summary' ? { ...it, undone: true } : it)))
    setFilesTick((n) => n + 1)
  }, [])

  /** Xoa luot cuoi cua nguoi dung (va moi thu sau no) tren server, tra ve noi dung de gui lai (tao lai / sua tin nhan). */
  const rewindLast = useCallback(async () => {
    const sid = sessionRef.current
    if (!sid) return null
    const s = await api.get<{ messages: WireMessage[] }>(`/api/sessions/${sid}`)
    let idx = -1
    s.messages.forEach((m, i) => { if (m.role === 'user') idx = i })
    if (idx < 0) return null
    const m = s.messages[idx]
    await api.post(`/api/sessions/${sid}/truncate`, { index: idx })
    setItems(fromWire(s.messages.slice(0, idx)))
    return { text: m.content, attachments: m.attachments ?? [] }
  }, [])

  return { sessionId, plan, items, busy, status, filesTick, send, stop, open, reset, decide, answer, undo, ensureSession, rewindLast, bumpFiles: () => setFilesTick((n) => n + 1) }
}
