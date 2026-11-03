import { useRef } from 'react'
import { Activity, FolderTree, PanelRightClose, Terminal } from 'lucide-react'
import { t, tk } from '@/lib/i18n.ts'
import { cn } from '@/lib/utils'
import { ActivityTab } from './ActivityTab'
import { FilesTab } from './FilesTab'
import { TerminalTab } from './TerminalTab'
import type { Item } from './useChat'

export type PanelTab = 'files' | 'terminal' | 'activity'

interface Props {
  sid: string | null
  items: Item[]
  filesTick: number
  tab: PanelTab
  onTab: (t: PanelTab) => void
  openPath: string | null
  onOpenPath: (p: string | null) => void
  onClose: () => void
  width: number
  onWidth: (w: number) => void
}

const TABS: { id: PanelTab; label: string; icon: typeof Terminal }[] = [
  { id: 'files', label: tk('Tệp'), icon: FolderTree },
  { id: 'terminal', label: tk('Terminal'), icon: Terminal },
  { id: 'activity', label: tk('Hoạt động'), icon: Activity },
]

export function WorkspacePanel({ sid, items, filesTick, tab, onTab, openPath, onOpenPath, onClose, width, onWidth }: Props) {
  const drag = useRef(false)
  const runs = items.filter((i) => i.kind === 'tool')
  const counts: Record<PanelTab, number> = { files: 0, terminal: runs.filter((i) => i.kind === 'tool' && i.name === 'exec').length, activity: runs.length }

  const onDown = (e: React.PointerEvent) => {
    drag.current = true
    ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
  }
  const onMove = (e: React.PointerEvent) => {
    if (drag.current) onWidth(Math.min(900, Math.max(300, window.innerWidth - e.clientX)))
  }

  return (
    <aside className="relative hidden shrink-0 flex-col border-l border-line bg-panel xl:flex" style={{ width }} aria-label={t('Không gian làm việc')}>
      <div onPointerDown={onDown} onPointerMove={onMove} onPointerUp={() => { drag.current = false }} role="separator" aria-orientation="vertical" aria-label={t('Kéo để đổi độ rộng')}
        className="absolute left-0 top-0 z-10 h-full w-1.5 cursor-col-resize transition hover:bg-accent/40" />
      <div className="flex h-14 shrink-0 items-center gap-1 border-b border-line px-2">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button key={id} onClick={() => onTab(id)} aria-pressed={tab === id}
            className={cn('flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-sm font-medium transition', tab === id ? 'bg-panel2 text-fg' : 'text-muted hover:text-fg')}>
            <Icon className="size-4" />{t(label)}{counts[id] > 0 && <span className="rounded bg-bg px-1 text-[10px] text-muted">{counts[id]}</span>}
          </button>
        ))}
        <button onClick={onClose} aria-label={t('Đóng panel')} className="ml-auto rounded p-1.5 text-muted hover:bg-panel2 hover:text-fg"><PanelRightClose className="size-4" /></button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {tab === 'files' && <FilesTab sid={sid} filesTick={filesTick} openPath={openPath} onOpenPath={onOpenPath} />}
        {tab === 'terminal' && <TerminalTab items={items} />}
        {tab === 'activity' && <ActivityTab items={items} />}
      </div>
    </aside>
  )
}
