import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Bell, Bot, Cable, Clock, FolderCog, House, LayoutDashboard, LogOut, MessageSquare, Moon, Plug, Puzzle, ScrollText, Settings, Sun, type LucideIcon } from 'lucide-react'
import { api } from '@/lib/api'
import { t, tk } from '@/lib/i18n.ts'
import { LangSwitcher } from './LangSwitcher'
import { cn } from '@/lib/utils'

const NAV: { to: string; label: string; icon: LucideIcon }[] = [
  { to: '/', label: tk('Trang chủ'), icon: House },
  { to: '/chat', label: tk('Trò chuyện'), icon: MessageSquare },
  { to: '/dashboard', label: tk('Bảng điều khiển'), icon: LayoutDashboard },
  { to: '/automations', label: tk('Tự động hóa'), icon: Clock },
  { to: '/skills', label: tk('Kỹ năng'), icon: Puzzle },
  { to: '/providers', label: tk('Nhà cung cấp'), icon: Plug },
  { to: '/integrations', label: tk('Tích hợp'), icon: Cable },
  { to: '/workspace', label: tk('Không gian làm việc'), icon: FolderCog },
  { to: '/notifications', label: tk('Hộp thư'), icon: Bell },
  { to: '/audit', label: tk('Nhật ký hoạt động'), icon: ScrollText },
  { to: '/settings', label: tk('Cài đặt'), icon: Settings },
]

function useTheme() {
  const [light, setLight] = useState(() => {
    try { return localStorage.getItem('theme') === 'light' } catch { return false }
  })
  useEffect(() => {
    document.documentElement.classList.toggle('light', light)
    try { localStorage.setItem('theme', light ? 'light' : 'dark') } catch { /* private mode */ }
  }, [light])
  return [light, setLight] as const
}

export function AppLayout() {
  const [light, setLight] = useTheme()
  const count = useQuery({ queryKey: ['notif-count'], queryFn: () => api.get<{ unread: number }>('/api/notifications/count'), refetchInterval: 15_000 })
  const auth = useQuery({ queryKey: ['auth-status'], queryFn: () => api.get<{ required: boolean }>('/api/auth/status') })
  const logout = () => { void api.post('/api/auth/logout').then(() => window.dispatchEvent(new Event('auth-required'))) }
  return (
    <div className="flex h-full">
      <aside className="flex w-14 shrink-0 flex-col border-r border-line bg-panel md:w-56">
        <div className="flex h-14 items-center gap-2.5 px-3.5 md:px-4">
          <div className="grid size-8 shrink-0 place-items-center rounded-lg bg-accent text-accent-fg"><Bot className="size-[18px]" /></div>
          <span className="hidden text-[15px] font-semibold tracking-tight md:block">Argus Agent</span>
        </div>
        <div className="px-2 pb-1"><LangSwitcher /></div>
        <nav className="flex flex-1 flex-col gap-0.5 px-2 py-2" aria-label={t('Điều hướng chính')}>
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              title={t(label)}
              className={({ isActive }) =>
                cn('flex h-9 items-center gap-3 rounded-lg px-2.5 text-sm font-medium transition', isActive ? 'bg-accent/12 text-accent' : 'text-muted hover:bg-panel2 hover:text-fg')
              }
            >
              <Icon className="size-[18px] shrink-0" />
              <span className="hidden md:block">{t(label)}</span>
              {to === '/notifications' && (count.data?.unread ?? 0) > 0 && <span className="ml-auto hidden rounded-full bg-accent px-1.5 text-[11px] font-semibold text-accent-fg md:block">{count.data?.unread}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="space-y-0.5 border-t border-line p-2">
          {auth.data?.required && (
            <button onClick={logout} title={t('Đăng xuất')} className="flex h-9 w-full items-center gap-3 rounded-lg px-2.5 text-sm text-muted transition hover:bg-panel2 hover:text-fg"><LogOut className="size-[18px] shrink-0" /><span className="hidden md:block">{t('Đăng xuất')}</span></button>
          )}
          <button
            onClick={() => setLight(!light)}
            title={light ? t('Giao diện tối') : t('Giao diện sáng')}
            className="flex h-9 w-full items-center gap-3 rounded-lg px-2.5 text-sm text-muted transition hover:bg-panel2 hover:text-fg"
          >
            {light ? <Moon className="size-[18px] shrink-0" /> : <Sun className="size-[18px] shrink-0" />}
            <span className="hidden md:block">{light ? t('Giao diện tối') : t('Giao diện sáng')}</span>
          </button>
        </div>
      </aside>
      <main className="min-w-0 flex-1"><Outlet /></main>
    </div>
  )
}
