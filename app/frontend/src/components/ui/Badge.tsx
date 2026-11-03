import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

const tones = {
  neutral: 'bg-panel2 text-muted border-line',
  ok: 'bg-ok/10 text-ok border-ok/25',
  warn: 'bg-warn/10 text-warn border-warn/25',
  bad: 'bg-bad/10 text-bad border-bad/25',
  info: 'bg-info/10 text-info border-info/25',
  accent: 'bg-accent/10 text-accent border-accent/25',
}

export function Badge({ tone = 'neutral', children, className }: { tone?: keyof typeof tones; children: ReactNode; className?: string }) {
  return <span className={cn('inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] font-medium leading-none', tones[tone], className)}>{children}</span>
}
