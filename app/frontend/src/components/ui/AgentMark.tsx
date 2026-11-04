import { cn } from '@/lib/utils'

/** Logo của Argus: một con mắt tối giản (vòng mống mắt và đồng tử) trên nền gradient. */
export function AgentMark({ size = 'lg', className }: { size?: 'sm' | 'lg'; className?: string }) {
  return (
    <svg
      viewBox="0 0 64 64"
      role="img"
      aria-label="Argus"
      className={cn('shrink-0', size === 'lg' ? 'size-14' : 'mt-0.5 size-8', className)}
    >
      <rect width="64" height="64" rx="14" fill="#e5412d"/>
<circle cx="32" cy="32" r="15" fill="none" stroke="#fff" strokeWidth="5.5"/>
<circle cx="32" cy="32" r="5.5" fill="#fff"/>
    </svg>
  )
}
