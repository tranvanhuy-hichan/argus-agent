import wordmark from '@/assets/argus-wordmark.png'
import mark from '@/assets/argus-mark.png'
import markLight from '@/assets/argus-mark-light.png'
import { cn } from '@/lib/utils'

/** Biểu tượng con cú trên ô vuông bo góc màu tím than (hợp cả giao diện tối lẫn sáng). */
export function AgentMark({ size = 'lg', className }: { size?: 'sm' | 'lg'; className?: string }) {
  return (
    <span role="img" aria-label="Argus" className={cn('grid shrink-0 place-items-center bg-gradient-to-br from-[#26245a] to-[#0e0d22] ring-1 ring-white/10', size === 'lg' ? 'size-14 rounded-xl' : 'mt-0.5 size-8 rounded-lg', className)}>
      <img src={mark} alt="" draggable={false} className={size === 'lg' ? 'w-[44px]' : 'w-[78%]'} />
    </span>
  )
}

/** Con cú Argus không có nền: bản sáng cho giao diện tối, bản navy cho giao diện sáng (đổi theo theme). */
export function AgentOwl({ className }: { className?: string }) {
  return (
    <span role="img" aria-label="Argus" className={cn('inline-flex shrink-0', className)}>
      <img src={mark} alt="" draggable={false} className="logo-on-dark h-full w-auto" />
      <img src={markLight} alt="" draggable={false} className="logo-on-light h-full w-auto" />
    </span>
  )
}

/** Logo đứng như bản gốc: con cú ở trên, chữ ARGUS ở dưới; không có nền và đổi màu theo giao diện. */
export function AgentLogoStacked({ className, large = false, xl = false }: { className?: string; large?: boolean; xl?: boolean }) {
  const url = `url(${wordmark})`
  return (
    <span role="img" aria-label="Argus" className={cn('flex flex-col items-center', xl ? 'gap-5' : 'gap-2', className)}>
      <AgentOwl className={xl ? 'h-28 sm:h-36' : large ? 'h-14' : 'h-10'} />
      <span aria-hidden className={cn('block bg-fg', xl ? 'h-8 sm:h-10' : large ? 'h-5' : 'h-[14px]')} style={{ aspectRatio: '7.33 / 1', WebkitMaskImage: url, maskImage: url, WebkitMaskSize: 'contain', maskSize: 'contain', WebkitMaskRepeat: 'no-repeat', maskRepeat: 'no-repeat' }} />
    </span>
  )
}

/** Logo ngang: con cú bên trái, chữ ARGUS bên phải; không có nền và đổi màu theo giao diện. */
export function AgentLogo({ className }: { className?: string }) {
  const url = `url(${wordmark})`
  return (
    <span role="img" aria-label="Argus" className={cn('flex items-center gap-3', className)}>
      <AgentOwl className="h-9" />
      <span aria-hidden className="block h-[17px] bg-fg" style={{ aspectRatio: '7.33 / 1', WebkitMaskImage: url, maskImage: url, WebkitMaskSize: 'contain', maskSize: 'contain', WebkitMaskRepeat: 'no-repeat', maskRepeat: 'no-repeat' }} />
    </span>
  )
}
