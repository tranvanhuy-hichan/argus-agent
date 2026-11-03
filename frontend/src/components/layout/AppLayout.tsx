import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { Bot, Cable, Clock, FolderCog, House, LayoutDashboard, MessageSquare, Moon, Plug, Puzzle, Settings, Sun, type LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

const NAV: { to: string; label: string; icon: LucideIcon }[] = [
  { to: '/', label: 'Trang chủ', icon: House },
  { to: '/chat', label: 'Chat', icon: MessageSquare },
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/automations', label: 'Automations', icon: Clock },
  { to: '/skills', label: 'Skills', icon: Puzzle },
  { to: '/providers', label: 'Providers', icon: Plug },
  { to: '/integrations', label: 'Tích hợp', icon: Cable },
  { to: '/workspace', label: 'Workspace', icon: FolderCog },
  { to: '/settings', label: 'Cài đặt', icon: Settings },
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
  return (
    <div className="flex h-full">
      <aside className="flex w-14 shrink-0 flex-col border-r border-line bg-panel md:w-56">
        <div className="flex h-14 items-center gap-2.5 px-3.5 md:px-4">
          <div className="grid size-8 shrink-0 place-items-center rounded-lg bg-accent text-accent-fg"><Bot className="size-[18px]" /></div>
          <span className="hidden text-[15px] font-semibold tracking-tight md:block">Agent</span>
        </div>
        <nav className="flex flex-1 flex-col gap-0.5 px-2 py-2" aria-label="Điều hướng chính">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              title={label}
              className={({ isActive }) =>
                cn('flex h-9 items-center gap-3 rounded-lg px-2.5 text-sm font-medium transition', isActive ? 'bg-accent/12 text-accent' : 'text-muted hover:bg-panel2 hover:text-fg')
              }
            >
              <Icon className="size-[18px] shrink-0" />
              <span className="hidden md:block">{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-line p-2">
          <button
            onClick={() => setLight(!light)}
            title={light ? 'Giao diện tối' : 'Giao diện sáng'}
            className="flex h-9 w-full items-center gap-3 rounded-lg px-2.5 text-sm text-muted transition hover:bg-panel2 hover:text-fg"
          >
            {light ? <Moon className="size-[18px] shrink-0" /> : <Sun className="size-[18px] shrink-0" />}
            <span className="hidden md:block">{light ? 'Giao diện tối' : 'Giao diện sáng'}</span>
          </button>
        </div>
      </aside>
      <main className="min-w-0 flex-1"><Outlet /></main>
    </div>
  )
}
