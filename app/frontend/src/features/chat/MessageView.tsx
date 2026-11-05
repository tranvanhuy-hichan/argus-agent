import { useState } from 'react'
import { AgentMark } from '../../components/ui/AgentMark'
import { Brain, Cable, HelpCircle, Undo2, Check, ChevronRight, ExternalLink, Eye, FileText, Globe, Info, Paperclip, Pencil, RefreshCw, ShieldAlert, Terminal, TriangleAlert, Wrench, X } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { BrandIcon, detectBrand } from '@/components/ui/BrandIcon'
import { Button } from '@/components/ui/Button'
import { t, tk } from '@/lib/i18n.ts'
import { T } from '@/lib/T.tsx'
import { cn } from '@/lib/utils'
import { Markdown } from './Markdown'
import { Images, SpeakButton } from './Media'
import { stripImageMarks } from './session'
import type { Item, ToolItem } from './useChat'

const KIND_LABEL: Record<string, string> = { http_request: tk('gửi yêu cầu HTTP thay đổi dữ liệu'), mcp: tk('gọi tool MCP'), exec: tk('chạy lệnh shell'), file_read: tk('đọc file ngoài workspace'), file_write: tk('ghi file'), browser: tk('điều khiển trình duyệt'), image: tk('tạo ảnh (có thể tốn phí)'), computer: tk('điều khiển máy tính (chuột, bàn phím, màn hình)') }
const RISK_ICON = { exec: Terminal, file: FileText, network: Globe, mcp: Cable } as const

export const fmtMs = (ms?: number) => (ms === undefined ? '' : ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`)

export function toolSummary(tool: ToolItem): string {
  if (tool.name === 'exec') return String(tool.args.command ?? '')
  if (typeof tool.args.path === 'string') return tool.args.path
  if (typeof tool.args.url === 'string') return tool.args.url
  if (typeof tool.args.query === 'string') return tool.args.query
  return JSON.stringify(tool.args)
}

function DecisionBadge({ d }: { d?: string }) {
  if (d === 'approved') return <Badge tone="ok">{t('Đã cho phép')}</Badge>
  if (d === 'denied') return <Badge tone="bad">{t('Bị từ chối')}</Badge>
  return null
}

/** Duong dan file cua phien ma agent nhac trong cau tra loi (".../sessions/<id>/ten.ext") -> duong dan tuong doi trong thu muc phien. */
function sessionFiles(text: string): string[] {
  const found = new Set<string>()
  for (const m of text.matchAll(/\/sessions\/[0-9a-f]{8}\/([^\s`"'*<>|)\]]+?\.[A-Za-z0-9]{1,6})(?=[\s`"'*)\],;:]|$)/g)) found.add(m[1])
  return [...found].slice(0, 6)
}
const NEW_TAB = /\.(html?|pdf|png|jpe?g|gif|svg|webp)$/i
const PREVIEWABLE = /\.(html?|svg)$/i

function LivePreviewModal({ path, sid, onClose }: { path: string; sid: string; onClose: () => void }) {
  const url = `/api/sessions/${sid}/file?path=${encodeURIComponent(path)}&raw=true`
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
      <div className="flex h-[85vh] w-full max-w-5xl flex-col rounded-2xl border border-line bg-panel shadow-2xl">
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <div className="flex items-center gap-2">
            <Eye className="size-4 text-accent" />
            <span className="font-semibold">{t('Xem trước: {name}', { name: path.split('/').pop() ?? path })}</span>
          </div>
          <div className="flex items-center gap-2">
            <a href={url} target="_blank" rel="noreferrer" className="flex items-center gap-1 rounded-lg border border-line px-2.5 py-1 text-xs text-muted hover:bg-panel2 hover:text-fg">
              <ExternalLink className="size-3.5" />
              {t('Tab mới')}
            </a>
            <button onClick={onClose} aria-label={t('Đóng')} className="rounded-lg p-1 text-muted hover:bg-panel2 hover:text-fg">
              <X className="size-4" />
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-hidden p-2">
          <iframe
            src={url}
            sandbox="allow-scripts allow-forms allow-same-origin"
            className="h-full w-full rounded-xl border border-line bg-white shadow-inner"
            title={path}
          />
        </div>
      </div>
    </div>
  )
}

function FileChips({ text, sid, onOpen }: { text: string; sid?: string | null; onOpen: (p: string) => void }) {
  const [preview, setPreview] = useState<string | null>(null)
  const files = sessionFiles(text)
  if (!files.length) return null
  return (
    <>
      <div className="mt-2 flex flex-wrap gap-2">
        {files.map((f) => (
          <span key={f} className="flex items-center overflow-hidden rounded-lg border border-line bg-panel text-xs">
            <button onClick={() => onOpen(f)} className="flex items-center gap-1.5 px-2.5 py-1.5 hover:bg-panel2"><FileText className="size-3.5 text-muted" /><span className="font-medium">{f.split('/').pop()}</span><span className="text-accent">{t('Mở')}</span></button>
            {sid && PREVIEWABLE.test(f) && <button onClick={() => setPreview(f)} className="flex items-center gap-1 border-l border-line px-2.5 py-1.5 text-accent hover:bg-panel2"><Eye className="size-3.5" />{t('Xem trước')}</button>}
            {sid && NEW_TAB.test(f) && <a href={`/api/sessions/${sid}/file?path=${encodeURIComponent(f)}&raw=true`} target="_blank" rel="noreferrer" className="flex items-center gap-1 border-l border-line px-2.5 py-1.5 text-muted hover:bg-panel2 hover:text-fg"><ExternalLink className="size-3.5" />{t('Tab mới')}</a>}
          </span>
        ))}
      </div>
      {preview && sid && <LivePreviewModal path={preview} sid={sid} onClose={() => setPreview(null)} />}
    </>
  )
}

/** Thay đổi file hiện ngay trong chat: edit = đoạn cũ/mới, write = nội dung ghi vào. */
function InlineDiff({ item }: { item: ToolItem }) {
  const a = item.args
  const lines = (txt: unknown, sign: '-' | '+') => String(txt ?? '').split('\n').map((l) => ({ sign, l }))
  let rows: { sign: '-' | '+'; l: string }[] = []
  if (item.name === 'edit') rows = [...lines(a.old, '-'), ...lines(a.new, '+')]
  else if (item.name === 'write') rows = lines(a.content, '+')
  if (!rows.length || item.ok === false) return null
  const MAX = 40
  return (
    <div className="mx-3 mb-2 overflow-hidden rounded-md border border-line bg-bg font-mono text-xs">
      <div className="max-h-72 overflow-auto">
        {rows.slice(0, MAX).map((r, i) => (
          <div key={i} className={cn('whitespace-pre-wrap break-all px-2', r.sign === '+' ? 'bg-ok/10 text-ok' : 'bg-bad/10 text-bad')}>{r.sign} {r.l}</div>
        ))}
        {rows.length > MAX && <div className="px-2 py-1 text-muted">{t('… còn {n} dòng nữa', { n: rows.length - MAX })}</div>}
      </div>
    </div>
  )
}

function ToolCard({ item, sid, onOpenFile }: { item: ToolItem; sid?: string | null; onOpenFile: (p: string) => void }) {
  const [open, setOpen] = useState(false)
  const [preview, setPreview] = useState<string | null>(null)
  const running = item.result === undefined
  const Icon = (item.risk && RISK_ICON[item.risk as keyof typeof RISK_ICON]) || Wrench
  const server = item.risk === 'mcp' ? item.name.split('__')[0] : null
  const path = (item.name === 'write' || item.name === 'edit') && typeof item.args.path === 'string' && !item.args.path.startsWith('/') ? item.args.path : null
  return (
    <div className="fade-in ml-10 rounded-lg border border-line bg-panel text-[13px]">
      <div className="flex w-full items-center gap-2 px-3 py-2">
        <button onClick={() => setOpen(!open)} className="flex min-w-0 flex-1 items-center gap-2 text-left" aria-expanded={open}>
          <ChevronRight className={cn('size-3.5 shrink-0 text-muted transition', open && 'rotate-90')} />
          <Icon className="size-3.5 shrink-0 text-muted" />
          <span className="font-medium">{server ? item.name.slice(server.length + 2) : item.name}</span>
          {server && <Badge tone="info">MCP · {server}</Badge>}
          <span className="min-w-0 flex-1 truncate font-mono text-xs text-muted">{toolSummary(item)}</span>
        </button>
        <DecisionBadge d={item.decision} />
        {item.duration !== undefined && <span className="text-[11px] tabular-nums text-muted">{fmtMs(item.duration)}</span>}
        {running ? <Badge tone="info">{t('đang chạy')}</Badge> : item.ok === false ? <Badge tone="bad">{t('lỗi')}</Badge> : <Badge tone="ok">{t('xong')}</Badge>}
        {path && <button onClick={() => onOpenFile(path)} className="rounded border border-line px-1.5 py-0.5 text-[11px] text-accent hover:bg-panel2">{t('Mở file')}</button>}
        {path && sid && PREVIEWABLE.test(path) && <button onClick={() => setPreview(path)} className="flex items-center gap-1 rounded border border-line px-1.5 py-0.5 text-[11px] text-accent hover:bg-panel2"><Eye className="size-3" />{t('Xem trước')}</button>}
      </div>
      {preview && sid && <LivePreviewModal path={preview} sid={sid} onClose={() => setPreview(null)} />}
      {(item.name === 'edit' || item.name === 'write') && <InlineDiff item={item} />}
      {item.result && <div className="px-3 pb-2"><Images text={item.result} onOpen={onOpenFile} /></div>}
      {open && (
        <div className="space-y-2 border-t border-line p-3">
          <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-xs text-muted">{JSON.stringify(item.args, null, 2)}</pre>
          {item.result !== undefined && <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-md bg-bg p-2 font-mono text-xs">{item.result || t('(trống)')}</pre>}
        </div>
      )}
    </div>
  )
}

/** To mau cac @dich-vu trong tin nhan cua nguoi dung. */
function WithMentions({ text }: { text: string }) {
  return <>{text.split(/((?<![\w@./-])@[a-z0-9][\w-]*)/).map((part, i) => (part.startsWith('@') ? <span key={i} className="font-medium text-accent">{part}</span> : part))}</>
}

function Thinking({ text, streaming, provider }: { text: string; streaming: boolean; provider?: string }) {
  const [open, setOpen] = useState(false)
  const show = open || streaming
  const brand = detectBrand(provider)
  return (
    <div className="fade-in ml-10 text-[13px]">
      <button onClick={() => setOpen(!open)} className="flex items-center gap-2 text-muted hover:text-fg" aria-expanded={show}>
        <span className="grid size-5 shrink-0 place-items-center rounded-md bg-panel2">
          <BrandIcon brand={brand} className="size-3.5" />
        </span>
        <Brain className={cn('size-3.5', streaming && 'animate-pulse text-accent')} />
        <span className="font-medium">{streaming ? t('Đang suy nghĩ…') : t('Đã suy nghĩ')}</span>
        <ChevronRight className={cn('size-3 transition', show && 'rotate-90')} />
      </button>
      {show && <p className="mt-1.5 max-h-48 overflow-auto whitespace-pre-wrap border-l-2 border-line pl-3 text-xs italic text-muted">{text}</p>}
    </div>
  )
}

function ApprovalCard({ item, onDecide }: { item: Extract<Item, { kind: 'approval' }>; onDecide: (aid: string, ok: boolean) => void }) {
  return (
    <div className="fade-in ml-10 rounded-lg border border-warn/40 bg-warn/5 p-3.5">
      <div className="flex items-center gap-2 text-sm font-medium"><ShieldAlert className="size-4 text-warn" /><T k="Agent muốn {action}" v={{ action: KIND_LABEL[item.approvalKind] ? t(KIND_LABEL[item.approvalKind]) : item.approvalKind }} /></div>
      <pre className="my-2.5 overflow-x-auto whitespace-pre-wrap rounded-md bg-bg p-2.5 font-mono text-xs">{item.detail}</pre>
      {item.status === 'pending' ? (
        <div className="flex gap-2">
          <Button size="sm" variant="primary" onClick={() => onDecide(item.aid, true)}>{t('Cho phép')}</Button>
          <Button size="sm" onClick={() => onDecide(item.aid, false)}>{t('Từ chối')}</Button>
        </div>
      ) : (
        <Badge tone={item.status === 'allowed' ? 'ok' : 'bad'}>{item.status === 'allowed' ? t('Đã cho phép') : t('Đã từ chối')}</Badge>
      )}
    </div>
  )
}

function QuestionCard({ item, onAnswer }: { item: Extract<Item, { kind: 'question' }>; onAnswer: (qid: string, text: string) => void }) {
  const [text, setText] = useState('')
  return (
    <div className="fade-in ml-10 rounded-lg border border-accent/40 bg-accent/5 p-3.5">
      <div className="flex items-start gap-2 text-sm font-medium"><HelpCircle className="mt-0.5 size-4 shrink-0 text-accent" />{item.question}</div>
      {item.answer === null ? (
        <div className="mt-2.5 space-y-2">
          {item.options.length > 0 && <div className="flex flex-wrap gap-2">{item.options.map((o) => <Button key={o} size="sm" variant="primary" onClick={() => onAnswer(item.qid, o)}>{o}</Button>)}</div>}
          <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (text.trim()) onAnswer(item.qid, text.trim()) }}>
            <input value={text} onChange={(e) => setText(e.target.value)} placeholder={t('Hoặc gõ câu trả lời khác…')} className="min-w-0 flex-1 rounded-md border border-line bg-bg px-2.5 py-1.5 text-sm outline-none focus:border-accent" />
            <Button size="sm" type="submit" disabled={!text.trim()}>{t('Gửi')}</Button>
          </form>
        </div>
      ) : <p className="mt-2 text-sm text-muted">{t('Bạn trả lời:')} <span className="text-fg">{item.answer}</span></p>}
    </div>
  )
}

function SummaryCard({ item, onUndo, canAct }: { item: Extract<Item, { kind: 'summary' }>; onUndo?: () => void; canAct?: boolean }) {
  const add = item.files.reduce((n, f) => n + f.added, 0)
  const del = item.files.reduce((n, f) => n + f.removed, 0)
  const [busy, setBusy] = useState(false)
  return (
    <div className="fade-in ml-10 rounded-lg border border-line bg-panel p-3 text-[13px]">
      <div className="flex items-center gap-2">
        <span className="font-medium">{t('Đã thay đổi {n} file', { n: item.files.length })}</span>
        <span className="font-mono text-xs text-ok">+{add}</span><span className="font-mono text-xs text-bad">−{del}</span>
        {item.undone ? <Badge tone="warn">{t('Đã hoàn tác')}</Badge> : onUndo && (
          <button disabled={!canAct || busy} onClick={() => { setBusy(true); onUndo() }} className="ml-auto flex items-center gap-1 rounded border border-line px-2 py-0.5 text-xs text-accent hover:bg-panel2 disabled:opacity-40"><Undo2 className="size-3" />{t('Hoàn tác lượt này')}</button>
        )}
      </div>
      <ul className="mt-1.5 space-y-0.5">
        {item.files.map((f) => (
          <li key={f.path} className="flex items-center gap-2 font-mono text-xs text-muted"><span className="min-w-0 flex-1 truncate" title={f.path}>{f.path.split('/').slice(-3).join('/')}</span>{f.status === 'new' && <Badge tone="info">{t('mới')}</Badge>}<span className="text-ok">+{f.added}</span><span className="text-bad">−{f.removed}</span></li>
        ))}
      </ul>
    </div>
  )
}

interface Props {
  item: Item
  sid?: string | null
  onDecide: (aid: string, ok: boolean) => void
  onOpenFile: (path: string) => void
  isLastUser?: boolean
  isLastAssistant?: boolean
  canAct?: boolean
  onEdit?: (text: string) => void
  onRegenerate?: () => void
  onAnswer?: (qid: string, text: string) => void
  onUndo?: () => void
}

export function MessageView({ item, sid, onDecide, onOpenFile, isLastUser, isLastAssistant, canAct, onEdit, onRegenerate, onAnswer, onUndo }: Props) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  switch (item.kind) {
    case 'user':
      return (
        <div className="fade-in group flex flex-col items-end gap-1">
          {editing ? (
            <div className="w-full max-w-[85%] space-y-2">
              <textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={3} className="w-full rounded-xl border border-accent bg-panel p-3 text-sm focus:outline-none" aria-label={t('Sửa tin nhắn')} />
              <div className="flex justify-end gap-2">
                <Button size="sm" onClick={() => setEditing(false)}><X className="size-3.5" />{t('Hủy')}</Button>
                <Button size="sm" variant="primary" disabled={!draft.trim()} onClick={() => { setEditing(false); onEdit?.(draft) }}><Check className="size-3.5" />{t('Gửi lại')}</Button>
              </div>
            </div>
          ) : (
            <>
              <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-md bg-accent/15 px-4 py-2.5"><WithMentions text={item.text} /></div>
              {item.attachments && item.attachments.length > 0 && (
                <div className="flex max-w-[85%] flex-wrap justify-end gap-1.5">
                  {item.attachments.map((a) => <button key={a} onClick={() => onOpenFile(a)} className="flex items-center gap-1 rounded-md border border-line bg-panel px-2 py-0.5 text-[11px] text-muted hover:text-fg"><Paperclip className="size-3" />{a.split('/').pop()}</button>)}
                </div>
              )}
              {isLastUser && canAct && <button onClick={() => { setDraft(item.text); setEditing(true) }} className="flex items-center gap-1 text-[11px] text-muted opacity-0 transition hover:text-fg focus:opacity-100 group-hover:opacity-100"><Pencil className="size-3" />{t('Sửa và gửi lại')}</button>}
            </>
          )}
        </div>
      )
    case 'assistant':
      return (
        <div className="fade-in group flex gap-3">
          <AgentMark size="sm" />
          <div className="min-w-0 flex-1 pt-0.5">
            <div className={cn(item.streaming && 'caret')}><Markdown text={stripImageMarks(item.text)} /></div>
            {!item.streaming && <Images text={item.text} onOpen={onOpenFile} />}
            {!item.streaming && <FileChips text={item.text} sid={sid} onOpen={onOpenFile} />}
            {!item.streaming && (
              <div className="mt-1.5 flex items-center gap-3 text-[11px] text-muted">
                {item.provider && <span>{t('qua {provider}', { provider: item.provider })}{item.duration ? ` · ${fmtMs(item.duration)}` : ''}</span>}
                <SpeakButton text={item.text} />
                {isLastAssistant && canAct && <button onClick={onRegenerate} className="flex items-center gap-1 hover:text-fg"><RefreshCw className="size-3" />{t('Tạo lại')}</button>}
              </div>
            )}
          </div>
        </div>
      )
    case 'thinking':
      return <Thinking text={item.text} streaming={item.streaming} provider={item.provider} />
    case 'tool':
      return <ToolCard item={item} sid={sid} onOpenFile={onOpenFile} />
    case 'approval':
      return <ApprovalCard item={item} onDecide={onDecide} />
    case 'question':
      return <QuestionCard item={item} onAnswer={onAnswer ?? (() => undefined)} />
    case 'summary':
      return <SummaryCard item={item} onUndo={onUndo} canAct={canAct} />
    case 'notice':
      return <p className="ml-10 flex items-center gap-1.5 text-xs text-muted"><Info className="size-3.5" />{item.text}</p>
    case 'error':
      return <p className="ml-10 flex items-start gap-1.5 rounded-lg border border-bad/30 bg-bad/10 px-3 py-2 text-sm text-bad"><TriangleAlert className="mt-0.5 size-4 shrink-0" />{item.text}</p>
  }
}
