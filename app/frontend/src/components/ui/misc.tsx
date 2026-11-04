import type { ReactNode } from 'react'
import { LoaderCircle, type LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

export function Spinner({ className }: { className?: string }) {
  return <LoaderCircle className={cn('size-5 animate-spin text-muted', className)} />
}

export function Loading() {
  return <div className="flex justify-center py-16"><Spinner /></div>
}

export function EmptyState({ icon: Icon, title, hint, action }: { icon: LucideIcon; title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 py-14 text-center">
      <div className="grid size-11 place-items-center rounded-xl bg-panel2 text-muted"><Icon className="size-5" /></div>
      <p className="font-medium">{title}</p>
      {hint && <p className="max-w-sm text-sm text-muted">{hint}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}

export function PageHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-[16rem] flex-1">
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}

export function Page({ children }: { children: ReactNode }) {
  return <div className="h-full overflow-y-auto"><div className="w-full px-4 py-6 sm:px-6 lg:px-8">{children}</div></div>
}

export function ErrorNote({ error }: { error: unknown }) {
  return <p className="rounded-lg border border-bad/30 bg-bad/10 px-3 py-2 text-sm text-bad">{error instanceof Error ? error.message : String(error)}</p>
}
