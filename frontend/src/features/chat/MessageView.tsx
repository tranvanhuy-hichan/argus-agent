import { useState } from 'react'
import { Bot, ChevronRight, ShieldAlert, Terminal, Wrench, TriangleAlert, Info } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { cn } from '@/lib/utils'
import { Markdown } from './Markdown'
import type { Item } from './useChat'

const KIND_LABEL: Record<string, string> = { mcp: 'gọi tool MCP', exec: 'chạy lệnh shell', file_read: 'đọc file ngoài workspace', file_write: 'ghi file ngoài workspace' }

function ToolCard({ item }: { item: Extract<Item, { kind: 'tool' }> }) {
  const [open, setOpen] = useState(false)
  const running = item.result === undefined
  const summary = item.name === 'exec' ? String(item.args.command ?? '') : JSON.stringify(item.args)
  return (
    <div className="fade-in ml-10 rounded-lg border border-line bg-panel text-[13px]">
      <button onClick={() => setOpen(!open)} className="flex w-full items-center gap-2 px-3 py-2 text-left" aria-expanded={open}>
        <ChevronRight className={cn('size-3.5 shrink-0 text-muted transition', open && 'rotate-90')} />
        {item.name === 'exec' ? <Terminal className="size-3.5 shrink-0 text-muted" /> : <Wrench className="size-3.5 shrink-0 text-muted" />}
        <span className="font-medium">{item.name}</span>
        <span className="min-w-0 flex-1 truncate font-mono text-xs text-muted">{summary}</span>
        {running ? <Badge tone="info">đang chạy</Badge> : item.ok === false ? <Badge tone="bad">lỗi</Badge> : <Badge tone="ok">xong</Badge>}
      </button>
      {open && (
        <div className="space-y-2 border-t border-line p-3">
          <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-xs text-muted">{JSON.stringify(item.args, null, 2)}</pre>
          {item.result !== undefined && <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-md bg-bg p-2 font-mono text-xs">{item.result || '(trống)'}</pre>}
        </div>
      )}
    </div>
  )
}

function ApprovalCard({ item, onDecide }: { item: Extract<Item, { kind: 'approval' }>; onDecide: (aid: string, ok: boolean) => void }) {
  return (
    <div className="fade-in ml-10 rounded-lg border border-warn/40 bg-warn/5 p-3.5">
      <div className="flex items-center gap-2 text-sm font-medium"><ShieldAlert className="size-4 text-warn" />Agent muốn {KIND_LABEL[item.approvalKind] ?? item.approvalKind}</div>
      <pre className="my-2.5 overflow-x-auto whitespace-pre-wrap rounded-md bg-bg p-2.5 font-mono text-xs">{item.detail}</pre>
      {item.status === 'pending' ? (
        <div className="flex gap-2">
          <Button size="sm" variant="primary" onClick={() => onDecide(item.aid, true)}>Cho phép</Button>
          <Button size="sm" onClick={() => onDecide(item.aid, false)}>Từ chối</Button>
        </div>
      ) : (
        <Badge tone={item.status === 'allowed' ? 'ok' : 'bad'}>{item.status === 'allowed' ? 'Đã cho phép' : 'Đã từ chối'}</Badge>
      )}
    </div>
  )
}

export function MessageView({ item, onDecide }: { item: Item; onDecide: (aid: string, ok: boolean) => void }) {
  switch (item.kind) {
    case 'user':
      return (
        <div className="fade-in flex justify-end">
          <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-md bg-accent/15 px-4 py-2.5">{item.text}</div>
        </div>
      )
    case 'assistant':
      return (
        <div className="fade-in flex gap-3">
          <div className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-lg bg-accent text-accent-fg"><Bot className="size-4" /></div>
          <div className="min-w-0 flex-1 pt-0.5">
            <div className={cn(item.streaming && 'caret')}><Markdown text={item.text} /></div>
            {item.provider && !item.streaming && <p className="mt-1.5 text-[11px] text-muted">via {item.provider}</p>}
          </div>
        </div>
      )
    case 'tool':
      return <ToolCard item={item} />
    case 'approval':
      return <ApprovalCard item={item} onDecide={onDecide} />
    case 'notice':
      return <p className="ml-10 flex items-center gap-1.5 text-xs text-muted"><Info className="size-3.5" />{item.text}</p>
    case 'error':
      return <p className="ml-10 flex items-start gap-1.5 rounded-lg border border-bad/30 bg-bad/10 px-3 py-2 text-sm text-bad"><TriangleAlert className="mt-0.5 size-4 shrink-0" />{item.text}</p>
  }
}
