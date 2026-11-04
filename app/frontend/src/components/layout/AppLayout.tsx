import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Bell, Cable, Clock, Code2, FolderCog, ListTodo, House, LayoutDashboard, LogOut, MessageSquare, Moon, Plug, Puzzle, Settings, Sun, type LucideIcon } from 'lucide-react'
import { api } from '@/lib/api'
import { t, tk } from '@/lib/i18n.ts'
import { AgentLogo, AgentOwl } from '@/components/ui/AgentMark'
import { LangSwitcher } from './LangSwitcher'
import { CODE_MODE } from '@/lib/features'
import { cn } from '@/lib/utils'

type NavItem = { to: string; label: string; icon: LucideIcon; hint: string }
const TOP: NavItem[] = [
  { to: '/', label: tk('Trang chủ'), icon: House, hint: tk('Tổng quan và việc nên làm tiếp') },
  { to: '/chat', label: tk('Trò chuyện'), icon: MessageSquare, hint: tk('Nói chuyện và giao việc cho agent') },
]
const GROUPS: { title: string; items: NavItem[] }[] = [
  { title: tk('Công việc'), items: [
    ...(CODE_MODE ? [{ to: '/code', label: tk('Lập trình'), icon: Code2, hint: tk('Mở một dự án và nhờ agent viết code') }] : []),
    { to: '/tasks', label: tk('Tác vụ'), icon: ListTodo, hint: tk('Việc dài agent làm ngầm') },
    { to: '/automations', label: tk('Tự động hóa'), icon: Clock, hint: tk('Việc lặp theo lịch') },
    { to: '/notifications', label: tk('Hộp thư'), icon: Bell, hint: tk('Thông báo từ agent') },
  ] },
  { title: tk('Khả năng của agent'), items: [
    { to: '/skills', label: tk('Kỹ năng'), icon: Puzzle, hint: tk('Dạy agent làm thêm việc mới') },
    { to: '/integrations', label: tk('Kết nối'), icon: Cable, hint: tk('Telegram, API, công cụ ngoài') },
    { to: '/workspace', label: tk('Tính cách & trí nhớ'), icon: FolderCog, hint: tk('Agent là ai và nhớ gì về bạn') },
  ] },
  { title: tk('Hệ thống'), items: [
    { to: '/providers', label: tk('Mô hình AI'), icon: Plug, hint: tk('Bộ não của agent: Gemini, Ollama…') },
    { to: '/activity', label: tk('Thống kê'), icon: LayoutDashboard, hint: tk('Agent đã làm gì, tốn bao nhiêu') },
    { to: '/settings', label: tk('Cài đặt'), icon: Settings, hint: tk('Tính năng, an toàn, mật khẩu') },
  ] },
]

function NavRow({ item: { to, label, icon: Icon, hint }, unread }: { item: NavItem; unread: number }) {
  return (
    <NavLink to={to} end={to === '/'} title={`${t(label)} — ${t(hint)}`}
      className={({ isActive }) => cn('flex h-9 items-center gap-3 rounded-lg px-2.5 text-sm font-medium transition', isActive ? 'bg-accent/12 text-accent' : 'text-muted hover:bg-panel2 hover:text-fg')}>
      <Icon className="size-[18px] shrink-0" />
      <span className="hidden md:block">{t(label)}</span>
      {unread > 0 && <span className="ml-auto hidden rounded-full bg-accent px-1.5 text-[11px] font-semibold text-accent-fg md:block">{unread}</span>}
    </NavLink>
  )
}

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
      <aside className="flex w-14 shrink-0 flex-col border-r border-line bg-panel/60 md:w-56">
        <NavLink to="/" aria-label={t('Về trang chủ')} title={t('Về trang chủ')} className="mx-2 mt-3 mb-3 flex shrink-0 items-center rounded-lg outline-offset-2 transition hover:opacity-80 md:mx-3 md:px-1">
          <AgentOwl className="h-8 md:hidden" />
          <AgentLogo className="hidden md:flex" />
        </NavLink>
        <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto px-2 py-2" aria-label={t('Điều hướng chính')}>
          {TOP.map((i) => <NavRow key={i.to} item={i} unread={0} />)}
          {GROUPS.map((g) => (
            <div key={g.title} className="mt-3">
              <p className="mb-1 hidden px-2.5 text-[11px] font-semibold uppercase tracking-wide text-muted/70 md:block">{t(g.title)}</p>
              <div className="mx-2 mb-1.5 border-t border-line md:hidden" />
              {g.items.map((i) => <NavRow key={i.to} item={i} unread={i.to === '/notifications' ? (count.data?.unread ?? 0) : 0} />)}
            </div>
          ))}
        </nav>
        <div className="space-y-0.5 border-t border-line p-2">
          <div className="hidden pb-1 md:block"><LangSwitcher /></div>
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
