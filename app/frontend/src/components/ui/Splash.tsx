import { AgentLogoStacked } from '@/components/ui/AgentMark'
import { t } from '@/lib/i18n.ts'
import { cn } from '@/lib/utils'

/** Khẩu hiệu luôn bằng tiếng Anh, không dịch theo ngôn ngữ giao diện. */
const SLOGAN = 'Intelligence that works the way you do.'

/** Màn hình chào: logo và tên lớn ở giữa kèm khẩu hiệu. Hiện ngay khi mở app và mờ dần khi dữ liệu đã sẵn sàng. */
export function Splash({ leaving }: { leaving: boolean }) {
  return (
    <div role="status" aria-label={t('Đang khởi động Argus…')} aria-live="polite"
      className={cn('fixed inset-0 z-[100] grid place-items-center bg-bg px-6 transition-opacity duration-500', leaving ? 'pointer-events-none opacity-0' : 'opacity-100')}>
      <div className="flex flex-col items-center text-center">
        <AgentLogoStacked xl />
        <p className="mt-8 max-w-md text-base text-muted sm:text-lg">{SLOGAN}</p>
        <div className="mt-10 h-0.5 w-40 overflow-hidden rounded-full bg-panel2" aria-hidden>
          <div className="splash-bar h-full w-1/3 rounded-full bg-accent" />
        </div>
      </div>
    </div>
  )
}
