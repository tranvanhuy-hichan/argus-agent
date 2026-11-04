import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Clock, Download, File as FileIcon, FileSearch, FileSpreadsheet, FileText, HeartPulse, MessageSquarePlus, Pencil, Pin, Presentation, Search, Send, Trash2, X } from 'lucide-react'
import { api } from '@/lib/api'
import type { KbDoc, SessionInfo } from '@/lib/types'
import { t } from '@/lib/i18n.ts'
import { cn, timeAgo } from '@/lib/utils'

interface Hit { session_id: string; role: string; snip: string; title: string }
interface KbList { docs: KbDoc[]; stats: { docs: number; chunks: number; indexing: number } }

const sourceIcon = (s: string) => (s === 'cron' ? <Clock className="size-3" /> : s === 'telegram' ? <Send className="size-3" /> : s === 'heartbeat' ? <HeartPulse className="size-3" /> : null)
const docIcon = (ext: string) => (ext === '.xlsx' || ext === '.xlsm' || ext === '.csv' || ext === '.tsv' ? FileSpreadsheet : ext === '.pptx' ? Presentation : ext === '.pdf' || ext === '.docx' || ext === '.txt' || ext === '.md' ? FileText : FileIcon)
const docSize = (n: number) => (n >= 1 << 20 ? `${(n / (1 << 20)).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`)

export function SessionList({ sessions, activeId, onOpen, onNew, onDeleted, showDocs }: { sessions: SessionInfo[]; activeId: string | null; onOpen: (id: string) => void; onNew: () => void; onDeleted: (id: string) => void; showDocs?: boolean }) {
  const qc = useQueryClient()
  const [q, setQ] = useState('')
  const [docQuery, setDocQuery] = useState('')
  const [debounced, setDebounced] = useState('')
  const [editing, setEditing] = useState<string | null>(null)
  const [title, setTitle] = useState('')
  useEffect(() => { const h = setTimeout(() => setDebounced(q.trim()), 300); return () => clearTimeout(h) }, [q])

  const hits = useQuery({ queryKey: ['search', debounced], queryFn: () => api.get<Hit[]>(`/api/search?q=${encodeURIComponent(debounced)}`), enabled: debounced.length >= 2 && !showDocs })
  const kbList = useQuery({ queryKey: ['kb'], queryFn: () => api.get<KbList>('/api/knowledge'), refetchInterval: 10_000, enabled: showDocs })
  const refresh = () => { void qc.invalidateQueries({ queryKey: ['sessions'] }) }
  const del = useMutation({ mutationFn: (id: string) => api.del(`/api/sessions/${id}`), onSuccess: refresh })
  const rename = useMutation({ mutationFn: (v: { id: string; title: string }) => api.patch(`/api/sessions/${v.id}`, { title: v.title }), onSuccess: () => { setEditing(null); refresh() } })
  const pin = useMutation({ mutationFn: (v: { id: string; pinned: boolean }) => api.post(`/api/sessions/${v.id}/pin`, { pinned: v.pinned }), onSuccess: refresh })
  const delDoc = useMutation({ mutationFn: (id: string) => api.del(`/api/knowledge/${id}`), onSuccess: () => void qc.invalidateQueries({ queryKey: ['kb'] }) })

  const filtered = sessions.filter((s) => !debounced || s.title.toLowerCase().includes(debounced.toLowerCase()))
  const docs = kbList.data?.docs ?? []
  const filteredDocs = docs.filter((d) => !docQuery.trim() || d.name.toLowerCase().includes(docQuery.toLowerCase()))

  if (showDocs) {
    return (
      <aside className="hidden w-72 shrink-0 flex-col border-r border-line bg-panel lg:flex">
        <div className="space-y-2 p-3">
          <div className="flex items-center gap-2 px-1 py-0.5">
            <FileSearch className="size-4 shrink-0 text-accent" />
            <span className="text-sm font-medium">{t('Tài liệu')}</span>
            {kbList.data?.stats && <span className="ml-auto text-[11px] text-muted">{kbList.data.stats.docs} {t('tài liệu')}</span>}
          </div>
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-2.5 size-3.5 text-muted" />
            <input value={docQuery} onChange={(e) => setDocQuery(e.target.value)} placeholder={t('Lọc tài liệu…')} aria-label={t('Lọc tài liệu')} className="h-8 w-full rounded-lg border border-line bg-bg pl-8 pr-2 text-xs placeholder:text-muted/70 focus:border-accent focus:outline-none" />
          </div>
        </div>
        <div className="flex-1 space-y-0.5 overflow-y-auto px-2 pb-3">
          {docs.length === 0 ? (
            <p className="px-3 py-6 text-center text-xs text-muted">{t('Chưa có tài liệu nào')}</p>
          ) : filteredDocs.length === 0 ? (
            <p className="px-3 py-6 text-center text-xs text-muted">{t('Không khớp tài liệu nào')}</p>
          ) : (
            filteredDocs.map((d) => {
              const Icon = docIcon(d.ext)
              return (
                <div key={d.id} className="group flex items-start gap-2 rounded-lg px-2.5 py-2 transition hover:bg-panel2">
                  <Icon className="mt-0.5 size-4 shrink-0 text-muted" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-medium" title={d.name}>{d.name}</p>
                    <p className="text-[11px] text-muted">{docSize(d.size)} · {timeAgo(d.added)}</p>
                    {d.status === 'indexing' && <p className="text-[11px] text-info">{t('Đang xử lý…')}</p>}
                    {d.status === 'error' && <p className="text-[11px] text-bad">{t('Lỗi')}</p>}
                  </div>
                  <a href={`/api/knowledge/${d.id}/file`} download aria-label={t('Tải về')} className="rounded p-1 text-muted opacity-0 transition hover:text-fg focus:opacity-100 group-hover:opacity-100"><Download className="size-3.5" /></a>
                  <button onClick={() => { if (confirm(t('Xóa "{name}" khỏi kho tài liệu?', { name: d.name }))) delDoc.mutate(d.id) }} aria-label={t('Xóa')} className="rounded p-1 text-muted opacity-0 transition hover:text-bad focus:opacity-100 group-hover:opacity-100"><Trash2 className="size-3.5" /></button>
                </div>
              )
            })
          )}
        </div>
      </aside>
    )
  }


  return (
    <aside className="hidden w-72 shrink-0 flex-col border-r border-line bg-panel lg:flex">
      <div className="space-y-2 p-3">
        <button onClick={onNew} className="flex h-9 w-full items-center gap-2 rounded-lg border border-line px-3 text-sm font-medium transition hover:border-accent hover:text-accent"><MessageSquarePlus className="size-4" />{t('Hội thoại mới')}</button>
        <div className="relative"><Search className="pointer-events-none absolute left-2.5 top-2.5 size-3.5 text-muted" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('Tìm hội thoại, nội dung…')} aria-label={t('Tìm hội thoại')} className="h-9 w-full rounded-lg border border-line bg-bg pl-8 pr-2 text-sm placeholder:text-muted/70 focus:border-accent focus:outline-none" /></div>
      </div>
      <div className="flex-1 space-y-0.5 overflow-y-auto px-2 pb-3">
        {filtered.map((s) => (
          <div key={s.id} className={cn('group flex items-start gap-1 rounded-lg px-2.5 py-2 transition hover:bg-panel2', s.id === activeId && 'bg-panel2')}>
            {editing === s.id ? (
              <>
                <input autoFocus value={title} onChange={(e) => setTitle(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') rename.mutate({ id: s.id, title }); if (e.key === 'Escape') setEditing(null) }} aria-label={t('Tên hội thoại')} className="min-w-0 flex-1 rounded border border-accent bg-bg px-1.5 py-0.5 text-sm focus:outline-none" />
                <button onClick={() => rename.mutate({ id: s.id, title })} aria-label={t('Lưu tên')} className="text-ok"><Check className="size-3.5" /></button>
                <button onClick={() => setEditing(null)} aria-label={t('Hủy')} className="text-muted"><X className="size-3.5" /></button>
              </>
            ) : (
              <>
                <button onClick={() => onOpen(s.id)} className="min-w-0 flex-1 text-left" title={s.title}>
                  <p className="flex items-start gap-1.5 text-sm">
                    {!!s.pinned && <Pin className="mt-0.5 size-3 shrink-0 rotate-45 fill-current text-accent" />}
                    <span className="line-clamp-2 text-sm leading-snug break-words font-medium">{s.title}</span>
                  </p>
                  <p className="mt-1 flex items-center gap-1 text-[11px] text-muted">{sourceIcon(s.source)}{timeAgo(s.updated)}</p>
                </button>
                <div className="flex shrink-0 items-center gap-0.5 pt-0.5">
                  <button onClick={(e) => { e.stopPropagation(); pin.mutate({ id: s.id, pinned: !s.pinned }) }} aria-label={s.pinned ? t('Bỏ ghim') : t('Ghim lên đầu')} title={s.pinned ? t('Bỏ ghim') : t('Ghim lên đầu')} className={cn('rounded p-1 transition hover:text-accent', s.pinned ? 'text-accent opacity-100' : 'text-muted opacity-0 group-hover:opacity-100')}><Pin className={cn('size-3.5', s.pinned && 'rotate-45 fill-current')} /></button>
                  <button onClick={() => { setEditing(s.id); setTitle(s.title) }} aria-label={t('Đổi tên')} className="rounded p-1 text-muted opacity-0 transition hover:text-fg focus:opacity-100 group-hover:opacity-100"><Pencil className="size-3.5" /></button>
                  <button onClick={() => { del.mutate(s.id); onDeleted(s.id) }} aria-label={t('Xóa hội thoại')} className="rounded p-1 text-muted opacity-0 transition hover:text-bad focus:opacity-100 group-hover:opacity-100"><Trash2 className="size-3.5" /></button>
                </div>
              </>
            )}
          </div>
        ))}
        {sessions.length === 0 && <p className="px-3 py-6 text-center text-xs text-muted">{t('Chưa có hội thoại nào')}</p>}
        {debounced.length >= 2 && (hits.data?.length ?? 0) > 0 && (
          <div className="mt-3 border-t border-line pt-3">
            <p className="px-2.5 pb-1 text-[11px] font-semibold uppercase tracking-wider text-muted">{t('Trong nội dung')}</p>
            {hits.data?.map((h, i) => (
              <button key={i} onClick={() => onOpen(h.session_id)} className="block w-full rounded-lg px-2.5 py-2 text-left hover:bg-panel2">
                <p className="line-clamp-2 text-xs font-medium leading-snug break-words">{h.title}</p>
                <p className="line-clamp-2 text-[11px] text-muted">{h.snip}</p>
              </button>
            ))}
          </div>
        )}
      </div>
    </aside>
  )
}
