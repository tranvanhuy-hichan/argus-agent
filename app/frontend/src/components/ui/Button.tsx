import type { ButtonHTMLAttributes } from 'react'
import { LoaderCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
const styles: Record<Variant, string> = {
  primary: 'bg-accent text-accent-fg hover:brightness-110',
  secondary: 'bg-panel2 text-fg border border-line hover:border-muted/50',
  ghost: 'text-muted hover:text-fg hover:bg-panel2',
  danger: 'bg-bad/15 text-bad border border-bad/30 hover:bg-bad/25',
}

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: 'sm' | 'md'
  loading?: boolean
}

export function Button({ variant = 'secondary', size = 'md', loading, className, children, disabled, ...rest }: Props) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={cn(
        'inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition disabled:opacity-50',
        size === 'sm' ? 'h-8 px-3 text-xs' : 'h-9 px-4 text-sm',
        styles[variant],
        className,
      )}
    >
      {loading && <LoaderCircle className="size-3.5 animate-spin" />}
      {children}
    </button>
  )
}
