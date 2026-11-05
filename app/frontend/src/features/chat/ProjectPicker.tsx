import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowUp, Folder, FolderGit2, GitBranch, Home } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Form'
import { Modal } from '@/components/ui/Modal'
import { api } from '@/lib/api'
import { t } from '@/lib/i18n.ts'
import type { BrowseResult, RecentProject } from '@/lib/types'
import { errMsg } from '@/lib/utils'

const shorten = (p: string) => p.replace(/^\/home\/[^/]+/, '~')

/** Chọn thư mục dự án khi bật chế độ Lập trình ngay trong chat. */
export function ProjectPicker({ open, onClose, onPick }: { open: boolean; onClose: () => void; onPick: (path: string) => void }) {
  const [path, setPath] = useState('')
  const [dir, setDir] = useState('')
  const recent = useQuery({ queryKey: ['code-recent'], queryFn: () => api.get<RecentProject[]>('/api/code/projects'), enabled: open })
  const browse = useQuery({ queryKey: ['code-browse', dir], queryFn: () => api.get<BrowseResult>(`/api/code/browse?path=${encodeURIComponent(dir)}`), retry: false, enabled: open })
  const b = browse.data
  return (
    <Modal open={open} onClose={onClose} title={t('Bật chế độ Lập trình: chọn thư mục dự án')}
      footer={<Button variant="primary" disabled={!b && !path.trim()} onClick={() => onPick(path.trim() || b!.path)}>{path.trim() ? t('Dùng đường dẫn này') : t('Dùng thư mục này')}</Button>}>
      <div className="space-y-4">
        <Input value={path} onChange={(e) => setPath(e.target.value)} placeholder={t('Dán đường dẫn thư mục, ví dụ ~/Projects/my-app')} aria-label={t('Đường dẫn dự án')} className="font-mono" />
        {!!recent.data?.length && (
          <div>
            <p className="mb-1.5 text-xs font-medium text-muted">{t('Dự án gần đây')}</p>
            <div className="flex flex-wrap gap-2">
              {recent.data.slice(0, 6).map((p) => (
                <button key={p.path} onClick={() => onPick(p.path)} title={p.path} className="flex items-center gap-1.5 rounded-lg border border-line bg-bg px-2.5 py-1.5 text-sm hover:border-accent/60">
                  <FolderGit2 className="size-4 text-accent" />{p.name}{p.branch && <span className="flex items-center gap-0.5 font-mono text-[11px] text-muted"><GitBranch className="size-3" />{p.branch}</span>}
                </button>
              ))}
            </div>
          </div>
        )}
        <div>
          <div className="mb-1.5 flex items-center gap-1 text-xs text-muted">
            <button onClick={() => setDir('')} aria-label={t('Thư mục nhà')} className="rounded p-1 hover:bg-panel2 hover:text-fg"><Home className="size-3.5" /></button>
            {b?.parent && <button onClick={() => setDir(b.parent!)} aria-label={t('Lên một cấp')} className="rounded p-1 hover:bg-panel2 hover:text-fg"><ArrowUp className="size-3.5" /></button>}
            <span className="min-w-0 flex-1 truncate font-mono" title={b?.path}>{b ? shorten(b.path) : ''}</span>
          </div>
          {browse.error ? <p className="text-sm text-bad">{errMsg(browse.error)}</p> : (
            <ul className="grid max-h-56 grid-cols-2 gap-1.5 overflow-y-auto">
              {b?.dirs.map((d) => (
                <li key={d.path}>
                  <button onClick={() => { setDir(d.path); setPath('') }} onDoubleClick={() => onPick(d.path)} title={d.path} className="flex w-full items-center gap-2 rounded-lg border border-line bg-bg px-2.5 py-1.5 text-left text-sm hover:border-accent/60">
                    {d.git ? <FolderGit2 className="size-4 shrink-0 text-accent" /> : <Folder className="size-4 shrink-0 text-muted" />}<span className="truncate">{d.name}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </Modal>
  )
}
