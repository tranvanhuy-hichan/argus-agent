import { cn } from '@/lib/utils'

/** Logo của Argus (thần trăm mắt): con mắt có mống lửa, phía trên là những "con mắt" nhỏ luôn canh chừng. */
export function AgentMark({ size = 'lg', className }: { size?: 'sm' | 'lg'; className?: string }) {
  return (
    <svg
      viewBox="0 0 64 64"
      role="img"
      aria-label="Argus"
      className={cn('shrink-0', size === 'lg' ? 'size-14 drop-shadow-[0_6px_14px_rgba(240,80,60,0.3)]' : 'mt-0.5 size-8', className)}
    >
      <defs>
      <linearGradient id="argus-bg" x1="8" y1="0" x2="56" y2="64" gradientUnits="userSpaceOnUse"><stop offset="0" stopColor="#2b1613"/><stop offset="1" stopColor="#0f0808"/></linearGradient>
      <linearGradient id="argus-rim" x1="6" y1="13" x2="58" y2="51" gradientUnits="userSpaceOnUse"><stop offset="0" stopColor="#ff7a5c"/><stop offset="1" stopColor="#f2b13d"/></linearGradient>
      <radialGradient id="argus-iris" cx="0.4" cy="0.35" r="0.8"><stop offset="0" stopColor="#ffc2ad"/><stop offset="0.45" stopColor="#f0503c"/><stop offset="1" stopColor="#9c1d14"/></radialGradient>
      </defs>
      <rect width="64" height="64" rx="16" fill="url(#argus-bg)"/>
      <rect x="0.75" y="0.75" width="62.5" height="62.5" rx="15.25" fill="none" stroke="#ff7a5c" strokeOpacity=".28" strokeWidth="1.5"/>
      <path d="M6 34C14 21 23 16 32 16s18 5 26 18c-8 13-17 18-26 18S14 47 6 34Z" fill="#0f0808" stroke="url(#argus-rim)" strokeWidth="3" strokeLinejoin="round"/>
      <circle cx="32" cy="34" r="11.5" fill="url(#argus-iris)"/>
      <circle cx="32" cy="34" r="4.8" fill="#0f0808"/>
      <circle cx="35.2" cy="30.8" r="1.7" fill="#fff" fillOpacity=".9"/>
      <g fill="#ffb199"><circle cx="19" cy="11" r="1.7"/><circle cx="32" cy="7" r="2.1"/><circle cx="45" cy="11" r="1.7"/></g>
    </svg>
  )
}
