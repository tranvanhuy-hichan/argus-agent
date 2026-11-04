import { useState } from 'react'
import { ChevronDown, ChevronRight, File, FileCode, FileImage, FileText, Folder, FolderOpen } from 'lucide-react'
import type { FileEntry, GitFile } from '@/lib/types'
import { cn } from '@/lib/utils'

const icon = (p: string) => /\.(png|jpe?g|gif|webp|svg|ico)$/i.test(p) ? FileImage : /\.(py|jsx?|tsx?|mjs|sh|json|html?|css|scss|sql|ya?ml|toml|go|rs|java|c|h|cpp|php|vue)$/i.test(p) ? FileCode : /\.(md|txt|pdf|rst)$/i.test(p) ? FileText : File
const TONE = { new: 'text-ok', modified: 'text-warn', deleted: 'text-bad' }

/** Cây thư mục kiểu IDE: thư mục thu gọn sẵn, file có thay đổi git được tô màu. */
export function ProjectTree({ files, active, changes, onOpen }: { files: FileEntry[]; active: string | null; changes: Map<string, GitFile['status']>; onOpen: (p: string) => void }) {
  const [open, setOpen] = useState<Set<string>>(new Set())
  const toggle = (p: string) => setOpen((s) => { const n = new Set(s); if (n.has(p)) n.delete(p); else n.add(p); return n })
  // thư mục chứa file đã thay đổi: đánh dấu để thấy từ xa
  const dirty = new Set<string>()
  for (const p of changes.keys()) { const parts = p.split('/'); for (let i = 1; i < parts.length; i++) dirty.add(parts.slice(0, i).join('/')) }
  const visible = (p: string) => { const parts = p.split('/'); for (let i = 1; i < parts.length; i++) if (!open.has(parts.slice(0, i).join('/'))) return false; return true }

  return (
    <ul className="py-1 text-[13px]" role="tree">
      {files.filter((f) => visible(f.path)).map((f) => {
        const depth = f.path.split('/').length - 1
        const name = f.path.split('/').pop()
        const st = changes.get(f.path)
        const Icon = f.dir ? (open.has(f.path) ? FolderOpen : Folder) : icon(f.path)
        return (
          <li key={f.path} role="treeitem" aria-expanded={f.dir ? open.has(f.path) : undefined}>
            <button onClick={() => (f.dir ? toggle(f.path) : onOpen(f.path))} style={{ paddingLeft: 8 + depth * 14 }} title={f.path}
              className={cn('flex h-[26px] w-full items-center gap-1.5 pr-2 text-left transition hover:bg-panel2', active === f.path && 'bg-accent/15 text-fg')}>
              {f.dir ? (open.has(f.path) ? <ChevronDown className="size-3.5 shrink-0 text-muted" /> : <ChevronRight className="size-3.5 shrink-0 text-muted" />) : <span className="w-3.5 shrink-0" />}
              <Icon className={cn('size-4 shrink-0', f.dir ? 'text-accent/80' : 'text-muted', st && TONE[st])} />
              <span className={cn('min-w-0 flex-1 truncate', st && TONE[st])}>{name}</span>
              {f.dir && dirty.has(f.path) && <span className="size-1.5 shrink-0 rounded-full bg-warn" aria-hidden />}
              {st && <span className={cn('shrink-0 text-[10px] font-semibold', TONE[st])}>{st === 'new' ? 'U' : st === 'deleted' ? 'D' : 'M'}</span>}
            </button>
          </li>
        )
      })}
    </ul>
  )
}
