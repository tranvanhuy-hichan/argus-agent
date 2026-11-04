import { Eye } from 'lucide-react'
import { cn } from '../../lib/utils'

/** Biểu tượng của agent: con mắt của Argus trên nền gradient. */
export function AgentMark({ size = 'lg', className }: { size?: 'sm' | 'lg'; className?: string }) {
  const big = size === 'lg'
  return (
    <div
      aria-hidden
      className={cn(
        'relative grid shrink-0 place-items-center bg-gradient-to-br from-accent via-accent to-amber-500 text-accent-fg ring-1 ring-white/20',
        big ? 'size-14 rounded-2xl shadow-lg shadow-accent/30' : 'mt-0.5 size-7 rounded-lg',
        className,
      )}
    >
      <Eye className={big ? 'size-7' : 'size-4'} strokeWidth={2} />
      {big && <span className="pointer-events-none absolute inset-0 rounded-2xl bg-gradient-to-b from-white/25 to-transparent" />}
    </div>
  )
}
