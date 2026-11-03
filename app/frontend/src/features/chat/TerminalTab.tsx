import { useEffect, useRef } from 'react'
import { LoaderCircle } from 'lucide-react'
import { t } from '@/lib/i18n.ts'
import { fmtMs } from './MessageView'
import type { Item, ToolItem } from './useChat'

export function TerminalTab({ items }: { items: Item[] }) {
  const runs = items.filter((i): i is ToolItem => i.kind === 'tool' && i.name === 'exec')
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => { end.current?.scrollIntoView({ block: 'end' }) }, [runs.length, runs[runs.length - 1]?.result])
  if (!runs.length) return <p className="p-6 text-center text-sm text-muted">{t('Mọi lệnh shell agent chạy sẽ hiện ở đây như một cửa sổ terminal.')}</p>
  return (
    <div className="h-full overflow-auto bg-bg p-3 font-mono text-[12.5px] leading-relaxed">
      {runs.map((r) => {
        const out = r.result ?? ''
        const failed = r.ok === false || /\[exit code \d+\]/.test(out)
        return (
          <div key={r.key} className="mb-3">
            <div className="flex gap-2"><span className="select-none text-ok">$</span><span className="whitespace-pre-wrap break-all">{String(r.args.command ?? '')}</span></div>
            {r.result === undefined ? <div className="flex items-center gap-1.5 text-muted"><LoaderCircle className="size-3 animate-spin" />{t('đang chạy…')}</div> : (
              <pre className={`whitespace-pre-wrap break-all pl-4 ${failed ? 'text-bad' : 'text-muted'}`}>{out}</pre>
            )}
            {r.result !== undefined && <div className="pl-4 text-[11px] text-muted/70">{fmtMs(r.duration)}{r.decision === 'denied' ? t(' · bị từ chối') : ''}</div>}
          </div>
        )
      })}
      <div ref={end} />
    </div>
  )
}
