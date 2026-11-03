import { useState } from 'react'
import { Cable, CircleCheck, CircleX, FileText, Globe, LoaderCircle, Terminal, Wrench } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { t } from '@/lib/i18n.ts'
import { cn } from '@/lib/utils'
import { fmtMs, toolSummary } from './MessageView'
import type { Item, ToolItem } from './useChat'

const ICON = { exec: Terminal, file: FileText, network: Globe, mcp: Cable } as const

export function ActivityTab({ items }: { items: Item[] }) {
  const calls = items.filter((i): i is ToolItem => i.kind === 'tool')
  const [open, setOpen] = useState<string | null>(null)
  if (!calls.length) return <p className="p-6 text-center text-sm text-muted">{t('Mọi lần gọi tool, MCP và xử lý của agent sẽ được ghi lại tại đây theo thứ tự thời gian.')}</p>
  return (
    <ol className="p-3">
      {calls.map((c, i) => {
        const Icon = (c.risk && ICON[c.risk as keyof typeof ICON]) || Wrench
        const running = c.result === undefined
        return (
          <li key={c.key} className="relative pb-3 pl-7 last:pb-0">
            {i < calls.length - 1 && <span className="absolute left-[11px] top-6 h-full w-px bg-line" aria-hidden />}
            <span className={cn('absolute left-0 top-0.5 grid size-[23px] place-items-center rounded-full border bg-panel', running ? 'border-info text-info' : c.ok === false ? 'border-bad text-bad' : 'border-ok text-ok')}>
              {running ? <LoaderCircle className="size-3 animate-spin" /> : c.ok === false ? <CircleX className="size-3" /> : <CircleCheck className="size-3" />}
            </span>
            <button onClick={() => setOpen(open === c.key ? null : c.key)} className="w-full text-left" aria-expanded={open === c.key}>
              <div className="flex items-center gap-1.5 text-sm"><Icon className="size-3.5 text-muted" /><span className="font-medium">{c.name}</span>
                {c.decision === 'approved' && <Badge tone="ok">{t('cho phép')}</Badge>}{c.decision === 'denied' && <Badge tone="bad">{t('từ chối')}</Badge>}
                <span className="ml-auto text-[11px] tabular-nums text-muted">{fmtMs(c.duration)}</span></div>
              <p className="truncate font-mono text-xs text-muted">{toolSummary(c)}</p>
            </button>
            {open === c.key && c.result !== undefined && <pre className="mt-1.5 max-h-48 overflow-auto whitespace-pre-wrap rounded-md bg-bg p-2 font-mono text-[11.5px]">{c.result || t('(trống)')}</pre>}
          </li>
        )
      })}
    </ol>
  )
}
