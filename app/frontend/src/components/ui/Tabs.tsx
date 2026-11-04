import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export function Tabs<T extends string>({ tabs, value, onChange, right }: { tabs: { id: T; label: string; count?: number }[]; value: T; onChange: (v: T) => void; right?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-2 border-b border-line">
    <div className="flex gap-1" role="tablist">
      {tabs.map((t) => (
        <button
          key={t.id}
          role="tab"
          aria-selected={value === t.id}
          onClick={() => onChange(t.id)}
          className={cn('-mb-px border-b-2 px-3.5 py-2 text-sm font-medium transition', value === t.id ? 'border-accent text-fg' : 'border-transparent text-muted hover:text-fg')}
        >
          {t.label}
          {t.count !== undefined && <span className="ml-1.5 rounded-md bg-panel2 px-1.5 py-0.5 text-[11px] text-muted">{t.count}</span>}
        </button>
      ))}
    </div>
    {right && <div className="pb-2">{right}</div>}
    </div>
  )
}
