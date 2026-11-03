import { useCallback, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { streamChat, type ChatEvent } from '@/lib/chatStream'
import type { WireMessage } from '@/lib/types'
import { errMsg } from '@/lib/utils'

export type Item =
  | { key: string; kind: 'user'; text: string }
  | { key: string; kind: 'assistant'; text: string; provider?: string; streaming?: boolean }
  | { key: string; kind: 'tool'; callId: string; name: string; args: Record<string, unknown>; result?: string; ok?: boolean }
  | { key: string; kind: 'approval'; aid: string; approvalKind: string; detail: string; status: 'pending' | 'allowed' | 'denied' }
  | { key: string; kind: 'notice' | 'error'; text: string }

let seq = 0
const k = () => `i${++seq}`

export function fromWire(msgs: WireMessage[]): Item[] {
  const results = new Map(msgs.filter((m) => m.role === 'tool').map((m) => [m.tool_call_id, m.content]))
  const out: Item[] = []
  for (const m of msgs) {
    if (m.role === 'user') out.push({ key: k(), kind: 'user', text: m.content })
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
  const abort = useRef<AbortController | null>(null)

  const apply = useCallback((e: ChatEvent) => {
    setItems((prev) => {
      const last = prev[prev.length - 1]
      switch (e.type) {
        case 'session':
          setSessionId(e.id)
          return prev
        case 'delta':
          if (last?.kind === 'assistant' && last.streaming) return [...prev.slice(0, -1), { ...last, text: last.text + e.text }]
          return [...prev, { key: k(), kind: 'assistant', text: e.text, streaming: true }]
        case 'assistant': {
          const done = { kind: 'assistant' as const, text: e.content, provider: e.provider, streaming: false }
          if (last?.kind === 'assistant' && last.streaming) return [...prev.slice(0, -1), { ...last, ...done }]
          return e.content ? [...prev, { key: k(), ...done }] : prev
        }
        case 'tool':
          return [...prev, { key: k(), kind: 'tool', callId: e.id, name: e.name, args: e.args }]
        case 'tool_result':
          return prev.map((it) => (it.kind === 'tool' && it.callId === e.id ? { ...it, result: e.result, ok: e.ok } : it))
        case 'approval':
          return [...prev, { key: k(), kind: 'approval', aid: e.id, approvalKind: e.kind, detail: e.detail, status: 'pending' }]
        case 'notice':
          return [...prev, { key: k(), kind: 'notice', text: e.message }]
        case 'error':
          return [...prev, { key: k(), kind: 'error', text: e.message }]
        default:
          return prev
      }
    })
  }, [])

  const send = useCallback(async (text: string, provider: string | null) => {
    if (busy || !text.trim()) return
    setBusy(true)
    setItems((p) => [...p, { key: k(), kind: 'user', text }])
    const ctl = new AbortController()
    abort.current = ctl
    try {
      await streamChat({ text, session: sessionId, provider }, apply, ctl.signal)
    } catch (e) {
      if (!ctl.signal.aborted) apply({ type: 'error', message: errMsg(e) })
    } finally {
      setItems((p) => p.map((it) => (it.kind === 'assistant' && it.streaming ? { ...it, streaming: false } : it)))
      setBusy(false)
      void qc.invalidateQueries({ queryKey: ['sessions'] })
      void qc.invalidateQueries({ queryKey: ['dashboard'] })
    }
  }, [apply, busy, qc, sessionId])

  const stop = useCallback(() => abort.current?.abort(), [])

  const open = useCallback(async (sid: string) => {
    const s = await api.get<{ messages: WireMessage[] }>(`/api/sessions/${sid}`)
    setSessionId(sid)
    setItems(fromWire(s.messages))
  }, [])

  const reset = useCallback(() => {
    abort.current?.abort()
    setSessionId(null)
    setItems([])
  }, [])

  const decide = useCallback(async (aid: string, ok: boolean) => {
    setItems((p) => p.map((it) => (it.kind === 'approval' && it.aid === aid ? { ...it, status: ok ? 'allowed' : 'denied' } : it)))
    await api.post(`/api/approvals/${aid}`, { ok })
  }, [])

  return { sessionId, items, busy, send, stop, open, reset, decide }
}
