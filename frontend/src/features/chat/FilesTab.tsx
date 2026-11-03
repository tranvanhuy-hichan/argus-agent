import { useQuery } from '@tanstack/react-query'
import { File, FileCode, FileImage, FileSpreadsheet, FileText, Folder, FolderOpen } from 'lucide-react'
import { useState } from 'react'
import { Loading } from '@/components/ui/misc'
import { api } from '@/lib/api'
import type { FileEntry } from '@/lib/types'
import { t } from '@/lib/i18n.ts'
import { cn, timeAgo } from '@/lib/utils'
import { FileViewer } from './FileViewer'

const icon = (p: string) => /\.(png|jpe?g|gif|webp|svg)$/i.test(p) ? FileImage : /\.(py|js|ts|tsx|sh|json|html?|css|sql|ya?ml|toml)$/i.test(p) ? FileCode : /\.(csv|xlsx?)$/i.test(p) ? FileSpreadsheet : /\.(md|txt|pdf|docx?)$/i.test(p) ? FileText : File

export function FilesTab({ sid, filesTick, openPath, onOpenPath }: { sid: string | null; filesTick: number; openPath: string | null; onOpenPath: (p: string | null) => void }) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())
  const q = useQuery({ queryKey: ['files', sid, filesTick], queryFn: () => api.get<FileEntry[]>(`/api/sessions/${sid}/files`), enabled: !!sid })
  if (!sid) return <p className="p-6 text-center text-sm text-muted">{t('Bắt đầu hội thoại để agent tạo file ở đây.')}</p>
  if (openPath) return <FileViewer sid={sid} path={openPath} onBack={() => onOpenPath(null)} />
  if (q.isLoading) return <Loading />
  const files = q.data ?? []
  if (files.length === 0) return <p className="p-6 text-center text-sm text-muted">{t('Chưa có file nào. Script, dữ liệu trung gian và kết quả agent tạo ra sẽ hiện ở đây, kèm cả file bạn đính kèm.')}</p>
  const hidden = (p: string) => [...collapsed].some((c) => p.startsWith(c + '/'))

  return (
    <ul className="p-2">
      {files.filter((f) => !hidden(f.path)).map((f) => {
        const depth = f.path.split('/').length - 1
        const Icon = f.dir ? (collapsed.has(f.path) ? Folder : FolderOpen) : icon(f.path)
        return (
          <li key={f.path}>
            <button
              onClick={() => (f.dir ? setCollapsed((s) => { const n = new Set(s); if (n.has(f.path)) n.delete(f.path); else n.add(f.path); return n }) : onOpenPath(f.path))}
              style={{ paddingLeft: 8 + depth * 14 }}
              className={cn('flex w-full items-center gap-2 rounded-lg py-1.5 pr-2 text-left text-sm transition hover:bg-panel2')}
            >
              <Icon className={cn('size-4 shrink-0', f.dir ? 'text-warn' : 'text-muted')} />
              <span className="min-w-0 flex-1 truncate">{f.path.split('/').pop()}</span>
              {!f.dir && <span className="shrink-0 text-[11px] text-muted">{f.size < 1024 ? `${f.size} B` : `${(f.size / 1024).toFixed(1)} KB`} · {timeAgo(f.mtime)}</span>}
            </button>
          </li>
        )
      })}
    </ul>
  )
}
