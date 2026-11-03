import { useState } from 'react'
import { Check, ChevronRight, Circle, CircleAlert, ListChecks, LoaderCircle } from 'lucide-react'
import { t } from '@/lib/i18n.ts'
import { cn } from '@/lib/utils'
import type { PlanItem } from '@/lib/types'

const ICON = { pending: Circle, in_progress: LoaderCircle, done: Check, blocked: CircleAlert }
const TONE = { pending: 'text-muted', in_progress: 'animate-spin text-accent', done: 'text-ok', blocked: 'text-bad' }

/** Ke hoach cua agent cho viec dai: hien tien do tung buoc ngay phia tren o soan tin. */
export function PlanCard({ items }: { items: PlanItem[] }) {
  const [open, setOpen] = useState(true)
  if (!items.length) return null
  const done = items.filter((i) => i.status === 'done').length
  return (
    <div className="mx-auto w-full max-w-4xl px-5 pb-2">
      <div className="rounded-xl border border-line bg-panel text-sm">
        <button onClick={() => setOpen(!open)} className="flex w-full items-center gap-2 px-3.5 py-2.5 text-left" aria-expanded={open}>
          <ChevronRight className={cn('size-3.5 text-muted transition', open && 'rotate-90')} />
          <ListChecks className="size-4 text-accent" />
          <span className="font-medium">{t('Kế hoạch')}</span>
          <span className="text-xs text-muted">{t('{done}/{total} bước xong', { done, total: items.length })}</span>
          <span className="ml-auto h-1.5 w-24 overflow-hidden rounded-full bg-panel2"><span className="block h-full bg-accent transition-all" style={{ width: `${(done / items.length) * 100}%` }} /></span>
        </button>
        {open && (
          <ol className="space-y-1 border-t border-line px-3.5 py-2.5">
            {items.map((it) => {
              const Icon = ICON[it.status]
              return (
                <li key={it.id} className="flex items-start gap-2">
                  <Icon className={cn('mt-0.5 size-3.5 shrink-0', TONE[it.status])} />
                  <span className={cn(it.status === 'done' && 'text-muted line-through')}>{it.text}{it.note && <span className="ml-1.5 text-xs text-muted">— {it.note}</span>}</span>
                </li>
              )
            })}
          </ol>
        )}
      </div>
    </div>
  )
}
