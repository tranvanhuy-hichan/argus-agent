import { useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BrainCircuit, Check, Copy, Download, Eye, File as FileIcon, FileSearch, FileSpreadsheet, FileText, Filter, FolderUp, MessagesSquare, Presentation, ScanSearch, Settings, Trash2, Upload } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { Field, Textarea } from '@/components/ui/Form'
import { Modal } from '@/components/ui/Modal'
import { Loading, Page, PageHeader } from '@/components/ui/misc'
import { SearchBox } from '@/components/ui/SearchBox'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import { t } from '@/lib/i18n.ts'
import type { KbDoc } from '@/lib/types'
import { cn, errMsg, timeAgo } from '@/lib/utils'

interface KbList { docs: KbDoc[]; stats: { docs: number; chunks: number; indexing: number }; supported: string[]; semantic: string | null }
interface ChunkItem { id: number; ord: number; loc: string; text: string }

const icon = (ext: string) => (ext === '.xlsx' || ext === '.xlsm' || ext === '.csv' || ext === '.tsv' ? FileSpreadsheet : ext === '.pptx' ? Presentation : ext === '.pdf' || ext === '.docx' || ext === '.txt' || ext === '.md' ? FileText : FileIcon)
const size = (n: number) => (n >= 1 << 20 ? `${(n / (1 << 20)).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`)

type Item = { file: File; name: string }

/** Thu mọi file trong một mục được thả vào (thư mục thì đi sâu vào trong). */
async function walk(entry: FileSystemEntry, prefix = ''): Promise<Item[]> {
  if (entry.isFile) {
    const file = await new Promise<File>((res, rej) => (entry as FileSystemFileEntry).file(res, rej))
    return [{ file, name: prefix + file.name }]
  }
  const reader = (entry as FileSystemDirectoryEntry).createReader()
  const out: Item[] = []
  for (;;) {
    const batch = await new Promise<FileSystemEntry[]>((res, rej) => reader.readEntries(res, rej))
    if (!batch.length) break
    for (const e of batch) if (!e.name.startsWith('.')) out.push(...(await walk(e, `${prefix}${entry.name}/`)))
  }
  return out
}

function ChunksModal({ doc, onClose }: { doc: KbDoc | null; onClose: () => void }) {
  const toast = useToast()
  const [copiedId, setCopiedId] = useState<number | null>(null)
  const q = useQuery({
    queryKey: ['kb-chunks', doc?.id],
    queryFn: () => api.get<{ doc: KbDoc; chunks: ChunkItem[] }>(`/api/knowledge/${doc!.id}/chunks`),
    enabled: !!doc,
  })

  const copyChunk = (id: number, text: string) => {
    navigator.clipboard.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 1500)
    toast(t('Đã chép đoạn trích'))
  }

  return (
    <Modal open={!!doc} onClose={onClose} wide title={doc ? `${t('Đoạn trích:')} ${doc.name}` : ''}
      footer={<Button onClick={onClose}>{t('Đóng')}</Button>}>
      {q.isLoading ? <Loading /> : q.error ? <p className="text-sm text-bad">{errMsg(q.error)}</p> : (
        <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-1">
          <div className="flex items-center justify-between text-xs text-muted border-b border-line pb-2">
            <span>{t('Tổng cộng {n} đoạn trích đã xử lý', { n: q.data?.chunks.length ?? 0 })}</span>
            <span>{t('Dùng để tìm kiếm ngữ nghĩa khi bạn trò chuyện')}</span>
          </div>
          {q.data?.chunks.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted">{t('Tài liệu này chưa có đoạn trích nào.')}</p>
          ) : (
            q.data?.chunks.map((c) => (
              <div key={c.id} className="rounded-lg border border-line bg-panel2/50 p-3.5 text-xs">
                <div className="mb-2 flex items-center justify-between font-mono text-[11px] text-muted">
                  <span className="font-semibold text-accent">#{c.ord + 1} {c.loc ? `· ${c.loc}` : ''}</span>
                  <div className="flex items-center gap-2">
                    <span>{c.text.length} {t('ký tự')}</span>
                    <button onClick={() => copyChunk(c.id, c.text)} className="flex items-center gap-1 rounded px-1.5 py-0.5 hover:bg-panel hover:text-fg">
                      {copiedId === c.id ? <Check className="size-3 text-ok" /> : <Copy className="size-3" />}
                      {copiedId === c.id ? t('Đã chép') : t('Chép')}
                    </button>
                  </div>
                </div>
                <p className="whitespace-pre-wrap break-words leading-relaxed text-fg">{c.text}</p>
              </div>
            ))
          )}
        </div>
      )}
    </Modal>
  )
}

export function DocumentsPage() {
  const qc = useQueryClient()
  const nav = useNavigate()
  const toast = useToast()
  const filePick = useRef<HTMLInputElement>(null)
  const dirPick = useRef<HTMLInputElement>(null)
  const [drag, setDrag] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [focus, setFocus] = useState('')
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null)
  const [filterQuery, setFilterQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | 'ready' | 'indexing' | 'error'>('all')
  const [previewDoc, setPreviewDoc] = useState<KbDoc | null>(null)

  const list = useQuery({ queryKey: ['kb'], queryFn: () => api.get<KbList>('/api/knowledge'), refetchInterval: (q) => (q.state.data?.stats.indexing ? 1500 : 10_000) })
  const supported = new Set(list.data?.supported ?? [])
  const refresh = () => void qc.invalidateQueries({ queryKey: ['kb'] })

  const upload = async (items: Item[]) => {
    const ok = items.filter((i) => supported.size === 0 || supported.has('.' + (i.name.split('.').pop() ?? '').toLowerCase()))
    const skipped = items.length - ok.length
    if (!ok.length) return toast(t('Không có file nào được hỗ trợ (PDF, Word, Excel, PowerPoint, văn bản).'), 'bad')
    let added = 0, dup = 0, failed = 0
    for (let i = 0; i < ok.length; i++) {
      setProgress({ done: i, total: ok.length })
      try {
        const r = await fetch(`/api/knowledge/upload?name=${encodeURIComponent(ok[i].name)}`, { method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: ok[i].file })
        if (!r.ok) throw new Error((await r.json().catch(() => ({ detail: r.statusText }))).detail)
        if ((await r.json()).duplicate) dup++; else added++
      } catch (e) {
        failed++
        toast(`${ok[i].name}: ${errMsg(e)}`, 'bad')
      }
    }
    setProgress(null)
    refresh()
    toast(t('Đã thêm {n} tài liệu', { n: added }) + (dup ? t(' · {n} trùng', { n: dup }) : '') + (skipped ? t(' · bỏ qua {n} file không hỗ trợ', { n: skipped }) : '') + (failed ? t(' · {n} lỗi', { n: failed }) : ''))
  }

  const onDrop = async (e: React.DragEvent) => {
    e.preventDefault()
    setDrag(false)
    const entries = [...e.dataTransfer.items].map((i) => i.webkitGetAsEntry?.()).filter((x): x is FileSystemEntry => !!x)
    const items = entries.length ? (await Promise.all(entries.map((x) => walk(x)))).flat() : [...e.dataTransfer.files].map((file) => ({ file, name: file.name }))
    void upload(items)
  }
  const fromInput = (files: FileList | null) => { if (files) void upload([...files].map((file) => ({ file, name: file.webkitRelativePath || file.name }))) }

  const analyze = useMutation({
    mutationFn: () => api.post<{ id: string }>('/api/knowledge/analyze', { focus }),
    onSuccess: () => { toast(t('Đã bắt đầu phân tích. Kết quả sẽ có ở trang Tác vụ.')); setAnalyzing(false); setFocus(''); nav('/tasks') },
    onError: (e) => toast(errMsg(e), 'bad'),
  })
  const del = useMutation({ mutationFn: (id: string) => api.del(`/api/knowledge/${id}`), onSuccess: refresh, onError: (e) => toast(errMsg(e), 'bad') })

  if (list.isLoading) return <Loading />
  const docs = list.data?.docs ?? []
  const stats = list.data?.stats
  const semantic = list.data?.semantic

  // Lọc tài liệu theo tên và trạng thái
  const filteredDocs = docs.filter((d) => {
    const matchName = !filterQuery.trim() || d.name.toLowerCase().includes(filterQuery.toLowerCase())
    const matchStatus = statusFilter === 'all' || d.status === statusFilter
    return matchName && matchStatus
  })

  return (
    <Page>
      <PageHeader title={t('Tài liệu')} action={
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => filePick.current?.click()}><Upload className="size-4" />{t('Chọn file')}</Button>
          <Button onClick={() => dirPick.current?.click()}><FolderUp className="size-4" />{t('Chọn thư mục')}</Button>
          <Button disabled={!stats?.docs} title={stats?.docs ? t('Đọc kỹ tài liệu, nêu rủi ro và đề xuất phương án (chạy nền)') : t('Thêm tài liệu trước khi hỏi')} onClick={() => setAnalyzing(true)}><ScanSearch className="size-4" />{t('Phân tích tài liệu')}</Button>
          <Button variant="primary" disabled={!stats?.docs} title={stats?.docs ? undefined : t('Thêm tài liệu trước khi hỏi')} onClick={() => nav('/chat', { state: { docs: true } })}><MessagesSquare className="size-4" />{t('Hỏi đáp về tài liệu')}</Button>
        </div>
      } />
      <input ref={filePick} type="file" multiple hidden accept={[...supported].join(',')} onChange={(e) => { fromInput(e.target.files); e.target.value = '' }} />
      <input ref={dirPick} type="file" hidden multiple {...({ webkitdirectory: '', directory: '' } as object)} onChange={(e) => { fromInput(e.target.files); e.target.value = '' }} />

      <div className="space-y-4">
        {/* Banner trạng thái Embedding */}
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-panel px-4 py-3 text-xs">
          <div className="flex items-center gap-2.5">
            <span className="grid size-7 place-items-center rounded-lg bg-accent/15 text-accent"><BrainCircuit className="size-4" /></span>
            <div>
              <span className="text-muted">{t('Tìm kiếm ngữ nghĩa (Semantic Vector):')} </span>
              {semantic ? (
                <span className="font-semibold text-ok">{semantic}</span>
              ) : (
                <span className="font-semibold text-warn">{t('Chưa bật (chỉ tìm theo từ khóa FTS5)')}</span>
              )}
              {stats && (
                <span className="ml-2 text-muted">· {t('{docs} tài liệu · {chunks} đoạn đã sẵn sàng', { docs: stats.docs, chunks: stats.chunks })}</span>
              )}
            </div>
          </div>
          <Link to="/settings?tab=features" className="flex items-center gap-1 font-medium text-accent hover:underline">
            <Settings className="size-3.5" />
            {t('Cài đặt mô hình Embedding')}
          </Link>
        </div>

        {/* Drag & Drop area */}
        <div onDragOver={(e) => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)} onDrop={(e) => void onDrop(e)}
          className={cn('grid place-items-center rounded-xl border-2 border-dashed px-6 py-8 text-center transition', drag ? 'border-accent bg-accent/5' : 'border-line bg-panel')}>
          <div>
            <FileSearch className="mx-auto mb-2 size-8 text-accent" />
            <p className="font-medium">{progress ? t('Đang tải {done}/{total}…', { done: progress.done + 1, total: progress.total }) : t('Kéo thả file hoặc thư mục vào đây')}</p>
            {progress && (
              <div className="mx-auto mt-3 h-2 w-64 overflow-hidden rounded-full bg-panel2">
                <div className="h-full bg-accent transition-all duration-300" style={{ width: `${Math.round(((progress.done + 1) / progress.total) * 100)}%` }} />
              </div>
            )}
            <p className="mt-1 text-sm text-muted">PDF · Word · Excel (.xlsx) · PowerPoint (.pptx) · TXT · Markdown · CSV</p>
          </div>
        </div>

        {!!stats?.indexing && (
          <div className="flex items-center gap-3 rounded-xl border border-info/30 bg-info/10 px-4 py-3 text-xs text-info">
            <span className="size-2 animate-ping rounded-full bg-info" />
            <span className="font-medium">{t('Đang phân tích đoạn trích và embedding {n} tài liệu (chạy nền)…', { n: stats.indexing })}</span>
          </div>
        )}

        {/* Thanh tìm kiếm & lọc */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="w-full sm:w-72">
            <SearchBox value={filterQuery} onChange={setFilterQuery} placeholder={t('Lọc tài liệu theo tên…')} label={t('Lọc tài liệu')} />
          </div>
          <div className="flex items-center gap-1.5 text-xs text-muted">
            <Filter className="size-3.5" />
            <span>{t('Trạng thái:')}</span>
            {(['all', 'ready', 'indexing', 'error'] as const).map((st) => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                className={cn('rounded-lg px-2.5 py-1 text-xs transition', statusFilter === st ? 'bg-accent text-accent-fg font-medium' : 'bg-panel2 text-muted hover:text-fg')}
              >
                {st === 'all' ? t('Tất cả') : st === 'ready' ? t('Sẵn sàng') : st === 'indexing' ? t('Đang xử lý') : t('Lỗi')}
              </button>
            ))}
          </div>
        </div>

        {/* Danh sách tài liệu */}
        <Card>
          <CardHeader title={t('Tài liệu đã thêm')} action={stats ? <span className="text-xs text-muted">{t('{docs} tài liệu · {chunks} đoạn', { docs: filteredDocs.length, chunks: stats.chunks })}</span> : undefined} />
          {docs.length === 0 ? (
            <p className="p-8 text-center text-sm text-muted">{t('Chưa có tài liệu nào. Kéo thả hợp đồng, báo cáo hoặc bảng tính vào ô phía trên để bắt đầu.')}</p>
          ) : filteredDocs.length === 0 ? (
            <p className="p-8 text-center text-sm text-muted">{t('Không tìm thấy tài liệu phù hợp với bộ lọc.')}</p>
          ) : (
            filteredDocs.map((d) => {
              const Icon = icon(d.ext)
              return (
                <div key={d.id} className="flex items-start gap-3 border-b border-line px-5 py-3 last:border-b-0">
                  <Icon className="mt-0.5 size-5 shrink-0 text-muted" />
                  <div className="min-w-0 flex-1">
                    <p className="flex flex-wrap items-center gap-2"><span className="truncate font-medium" title={d.name}>{d.name}</span>
                      {d.status === 'ready' ? <Badge tone="ok">{t('Sẵn sàng')}</Badge> : d.status === 'indexing' ? <Badge tone="info">{t('Đang xử lý…')}</Badge> : <Badge tone="bad">{t('Lỗi')}</Badge>}</p>
                    <p className="mt-0.5 text-xs text-muted">{size(d.size)}{d.pages && (d.ext === '.pdf' || d.ext === '.pptx') ? ` · ${t('{n} trang', { n: d.pages })}` : ''}{d.chunks ? ` · ${t('{n} đoạn', { n: d.chunks })}` : ''} · {timeAgo(d.added)}</p>
                    {d.note && <p className={cn('mt-1 text-xs', d.status === 'error' ? 'text-bad' : 'text-warn')}>{d.note}</p>}
                  </div>
                  <button onClick={() => setPreviewDoc(d)} aria-label={t('Xem đoạn trích')} title={t('Xem các đoạn trích')} className="rounded p-1.5 text-muted hover:bg-panel2 hover:text-accent"><Eye className="size-4" /></button>
                  <a href={`/api/knowledge/${d.id}/file`} download aria-label={t('Tải về')} title={t('Tải về file gốc')} className="rounded p-1.5 text-muted hover:bg-panel2 hover:text-fg"><Download className="size-4" /></a>
                  <button onClick={() => { if (confirm(t('Xóa "{name}" khỏi kho tài liệu?', { name: d.name }))) del.mutate(d.id) }} aria-label={t('Xóa')} title={t('Xóa tài liệu')} className="rounded p-1.5 text-muted hover:bg-panel2 hover:text-bad"><Trash2 className="size-4" /></button>
                </div>
              )
            })
          )}
        </Card>
      </div>

      <ChunksModal doc={previewDoc} onClose={() => setPreviewDoc(null)} />

      <Modal open={analyzing} onClose={() => setAnalyzing(false)} title={t('Phân tích tài liệu và đề xuất phương án')}
        footer={<><Button onClick={() => setAnalyzing(false)}>{t('Hủy')}</Button><Button variant="primary" loading={analyze.isPending} onClick={() => analyze.mutate()}><ScanSearch className="size-4" />{t('Bắt đầu phân tích')}</Button></>}>
        <div className="space-y-3">
          <Field label={t('Bạn muốn phân tích điều gì? (không bắt buộc)')}>
            <Textarea rows={3} value={focus} onChange={(e) => setFocus(e.target.value)} placeholder={t('Ví dụ: Phân tích rủi ro và đề xuất phương án thực hiện trong 90 ngày.')} />
          </Field>
          <p className="text-sm text-muted">{t('Argus đọc kỹ các tài liệu, rồi viết báo cáo gồm: tóm tắt, yêu cầu chính, rủi ro, các phương án, khuyến nghị và các bước thực hiện, kèm nguồn. Việc này chạy nền (có thể mất vài phút); kết quả xem ở trang Tác vụ.')}</p>
        </div>
      </Modal>
    </Page>
  )
}
