import type { PlanItem } from './types'

export type ChatEvent =
  | { type: 'session'; id: string }
  | { type: 'status'; text: string; tpl?: string; vars?: Record<string, string | number> }
  | { type: 'thinking'; text: string }
  | { type: 'delta'; text: string }
  | { type: 'assistant'; content: string; provider: string; usage: { prompt: number; completion: number }; duration_ms?: number }
  | { type: 'tool'; id: string; name: string; args: Record<string, unknown>; risk?: string }
  | { type: 'tool_result'; id: string; result: string; ok: boolean; duration_ms?: number; decision?: string }
  | { type: 'approval'; id: string; kind: string; detail: string }
  | { type: 'question'; id: string; question: string; options: string[] }
  | { type: 'question_done'; id: string; answer: string }
  | { type: 'turn_summary'; files: { path: string; status: string; added: number; removed: number }[] }
  | { type: 'approval_done'; id: string; ok: boolean }
  | { type: 'files' }
  | { type: 'plan'; items: PlanItem[] }
  | { type: 'notice'; message: string; tpl?: string; vars?: Record<string, string | number> }
  | { type: 'error'; message: string; tpl?: string; vars?: Record<string, string | number> }
  | { type: 'done' }

export async function streamChat(
  body: { text: string; session: string | null; provider: string | null; attachments?: string[]; permission?: string; effort?: string },
  onEvent: (e: ChatEvent) => void,
  signal: AbortSignal,
) {
  const r = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal })
  if (r.status === 401) window.dispatchEvent(new Event('auth-required'))
  if (!r.ok || !r.body) throw new Error(`HTTP ${r.status}`)
  const reader = r.body.getReader()
  const dec = new TextDecoder()
  let buf = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true })
    let i: number
    while ((i = buf.indexOf('\n\n')) >= 0) {
      const frame = buf.slice(0, i)
      buf = buf.slice(i + 2)
      if (frame.startsWith('data: ')) onEvent(JSON.parse(frame.slice(6)) as ChatEvent)
    }
  }
}

export type RunState = { active: boolean; cursor: number; pending: { id: string; kind: string; detail: string }[]; questions?: { id: string; question: string; options: string[] }[] }

async function readSse(r: Response, onEvent: (e: ChatEvent) => void) {
  if (r.status === 401) window.dispatchEvent(new Event('auth-required'))
  if (!r.ok || !r.body) throw new Error(`HTTP ${r.status}`)
  const reader = r.body.getReader()
  const dec = new TextDecoder()
  let buf = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true })
    let i: number
    while ((i = buf.indexOf('\n\n')) >= 0) {
      const frame = buf.slice(0, i)
      buf = buf.slice(i + 2)
      if (frame.startsWith('data: ')) onEvent(JSON.parse(frame.slice(6)) as ChatEvent)
    }
  }
}

/** Noi lai luong cua luot dang chay tren server (sau khi doi trang / doi phien). */
export async function attachChat(sid: string, start: number, onEvent: (e: ChatEvent) => void, signal: AbortSignal) {
  await readSse(await fetch(`/api/sessions/${sid}/attach?start=${start}`, { signal }), onEvent)
}
