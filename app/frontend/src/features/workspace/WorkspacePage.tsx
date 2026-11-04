import { useEffect, useState } from 'react'
import { ChevronRight, Code2, Download, Eye, Folder, FolderOpen, File as FileIcon, FileSpreadsheet, FileText, Image as ImageIcon, Sparkles, Trash2 } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { Modal } from '@/components/ui/Modal'
import { Textarea } from '@/components/ui/Form'
import { Loading, Page, PageHeader } from '@/components/ui/misc'
import { Tabs } from '@/components/ui/Tabs'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import type { Curation } from '@/lib/types'
import { errMsg, timeAgo } from '@/lib/utils'
import { t, tk } from '@/lib/i18n.ts'

const FILES = [
  { id: 'SOUL.md', label: 'SOUL', hint: tk('Tính cách, giọng điệu và quy tắc làm việc của agent. Luôn nằm trong prompt.') },
  { id: 'USER.md', label: 'USER', hint: tk('Thông tin về bạn (tên, sở thích, bối cảnh công việc) để agent cá nhân hóa câu trả lời.') },
  { id: 'HEARTBEAT.md', label: 'HEARTBEAT', hint: tk('Danh sách việc agent tự kiểm tra mỗi lần heartbeat (bật ở trang Tự động hóa). Mỗi dòng là một việc; xóa hết để tạm dừng.') },
  { id: 'MEMORY.md', label: 'MEMORY', hint: tk('Bộ nhớ dài hạn. Agent tự ghi vào đây khi bạn nhờ “hãy nhớ…”. Bạn có thể sửa hoặc xóa.') },
] as const

interface WsFile {
  path: string
  name: string
  size: number
  mtime: number
  is_system: boolean
  readonly?: boolean
  ext: string
}

interface TreeNode { name: string; path: string; folders: TreeNode[]; files: WsFile[]; count: number }

function buildTree(files: WsFile[]): TreeNode {
  const root: TreeNode = { name: '', path: '', folders: [], files: [], count: 0 }
  for (const f of files) {
    const parts = f.path.split('/')
    let node = root
    node.count++
    for (let i = 0; i < parts.length - 1; i++) {
      const path = parts.slice(0, i + 1).join('/')
      let next = node.folders.find((x) => x.path === path)
      if (!next) { next = { name: parts[i], path, folders: [], files: [], count: 0 }; node.folders.push(next) }
      next.count++
      node = next
    }
    node.files.push(f)
  }
  const sort = (n: TreeNode) => { n.folders.sort((a, b) => a.name.localeCompare(b.name)); n.files.sort((a, b) => a.name.localeCompare(b.name)); n.folders.forEach(sort) }
  sort(root)
  return root
}

const fmtSize = (n: number) => (n >= 1 << 20 ? `${(n / (1 << 20)).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`)

const fileIcon = (ext: string) => {
  if (['.py', '.js', '.ts', '.sh', '.html', '.css', '.json'].includes(ext)) return Code2
  if (['.csv', '.tsv', '.xlsx'].includes(ext)) return FileSpreadsheet
  if (['.png', '.jpg', '.jpeg', '.webp', '.svg'].includes(ext)) return ImageIcon
  if (['.md', '.txt', '.log'].includes(ext)) return FileText
  return FileIcon
}

function CurateButton({ onApplied }: { onApplied: () => void }) {
  const toast = useToast()
  const [res, setRes] = useState<Curation | null>(null)
  const propose = useMutation({ mutationFn: () => api.post<Curation>('/api/memory/curate', {}), onSuccess: (r) => { if (r.ok) setRes(r); else toast(r.reason || t('Không dọn được'), 'bad') }, onError: (e) => toast(errMsg(e), 'bad') })
  const apply = useMutation({
    mutationFn: () => api.post('/api/memory/curate/apply', { new: res?.new ?? '' }),
    onSuccess: () => { toast(t('Đã áp dụng. Bản cũ được lưu thành MEMORY.md.bak-…')); setRes(null); onApplied() },
    onError: (e) => toast(errMsg(e), 'bad'),
  })
  return (
    <>
      <Button loading={propose.isPending} onClick={() => propose.mutate()}><Sparkles className="size-4" />{t('Dọn bằng AI')}</Button>
      <Modal open={!!res} onClose={() => setRes(null)} wide title={t('Đề xuất dọn trí nhớ')}
        footer={<><Button onClick={() => setRes(null)}>{t('Hủy')}</Button><Button variant="primary" loading={apply.isPending} onClick={() => apply.mutate()}>{t('Áp dụng')}</Button></>}>
        {res && (
          <div className="space-y-3 text-sm">
            <div><p className="mb-1 font-medium text-bad">{t('Sẽ bỏ ({n})', { n: res.removed.length })}</p>{res.removed.length ? <ul className="list-disc space-y-0.5 pl-5 text-muted">{res.removed.map((x) => <li key={x}>{x}</li>)}</ul> : <p className="text-muted">—</p>}</div>
            <div><p className="mb-1 font-medium text-ok">{t('Sẽ thêm/viết lại ({n})', { n: res.added.length })}</p>{res.added.length ? <ul className="list-disc space-y-0.5 pl-5 text-muted">{res.added.map((x) => <li key={x}>{x}</li>)}</ul> : <p className="text-muted">—</p>}</div>
          </div>
        )}
      </Modal>
    </>
  )
}

function Editor({ file }: { file: string }) {
  const qc = useQueryClient()
  const toast = useToast()
  const q = useQuery({ queryKey: ['file', file], queryFn: () => api.get<{ content: string }>(`/api/workspace/${file}`) })
  const [text, setText] = useState('')
  useEffect(() => { if (q.data) setText(q.data.content) }, [q.data])
  const save = useMutation({
    mutationFn: () => api.put(`/api/workspace/${file}`, { content: text }),
    onSuccess: () => { toast(t('Đã lưu {file}', { file })); void qc.invalidateQueries({ queryKey: ['file', file] }) },
    onError: (e) => toast(errMsg(e), 'bad'),
  })
  if (q.isLoading) return <Loading />
  return (
    <Card className="p-5">
      <Textarea rows={18} value={text} onChange={(e) => setText(e.target.value)} aria-label={file} />
      <div className="mt-4 flex items-center gap-3">
        <Button variant="primary" loading={save.isPending} disabled={text === q.data?.content} onClick={() => save.mutate()}>{t('Lưu')}</Button>
        {file === 'MEMORY.md' && <CurateButton onApplied={() => void qc.invalidateQueries({ queryKey: ['file', file] })} />}
        <span className="text-xs text-muted">{t('{n} ký tự', { n: text.length.toLocaleString() })}{text.length > 4000 && file !== 'SOUL.md' ? t(' · chỉ 4000 ký tự cuối được đưa vào prompt') : ''}</span>
      </div>
    </Card>
  )
}

function WorkspaceFilesBrowser() {
  const qc = useQueryClient()
  const toast = useToast()
  const [viewingFile, setViewingFile] = useState<WsFile | null>(null)
  const [previewContent, setPreviewContent] = useState<string | null>(null)
  const [loadingPreview, setLoadingPreview] = useState(false)
  const [opened, setOpened] = useState<Set<string>>(new Set())
  const toggle = (path: string) => setOpened((s) => { const n = new Set(s); if (n.has(path)) n.delete(path); else n.add(path); return n })

  const q = useQuery({
    queryKey: ['workspace-files'],
    queryFn: () => api.get<{ files: WsFile[] }>('/api/workspace-files'),
  })

  const del = useMutation({
    mutationFn: (path: string) => api.del(`/api/workspace-files?path=${encodeURIComponent(path)}`),
    onSuccess: () => {
      toast(t('Đã xóa tệp'))
      void qc.invalidateQueries({ queryKey: ['workspace-files'] })
    },
    onError: (e) => toast(errMsg(e), 'bad'),
  })

  const openPreview = async (f: WsFile) => {
    setViewingFile(f)
    setLoadingPreview(true)
    setPreviewContent(null)
    try {
      const res = await fetch(`/api/workspace-files/download?path=${encodeURIComponent(f.path)}`)
      if (!res.ok) throw new Error(res.statusText)
      const text = await res.text()
      setPreviewContent(text)
    } catch (e) {
      setPreviewContent(t('Không thể đọc trước nội dung tệp này.'))
    } finally {
      setLoadingPreview(false)
    }
  }

  if (q.isLoading) return <Loading />
  const files = q.data?.files ?? []

  const tree = buildTree(files)
  const renderFile = (f: WsFile, depth: number) => {
    const Icon = fileIcon(f.ext)
    return (
      <div key={f.path} className="flex items-center gap-3 py-2 pr-5 transition hover:bg-panel2/50" style={{ paddingLeft: 20 + depth * 18 }}>
                  <Icon className="size-4 shrink-0 text-muted" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate font-mono text-xs font-medium text-fg">{f.name}</span>
                      {f.is_system ? <Badge tone="info">{t('Hệ thống')}</Badge> : f.readonly && <Badge>{t('Chỉ xem')}</Badge>}
                    </div>
                    <p className="mt-0.5 text-[11px] text-muted">
                      {fmtSize(f.size)} · {timeAgo(f.mtime)}
                    </p>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => openPreview(f)}
                      title={t('Xem trước')}
                      aria-label={t('Xem trước')}
                      className="rounded p-1.5 text-muted hover:bg-panel hover:text-accent"
                    >
                      <Eye className="size-3.5" />
                    </button>
                    <a
                      href={`/api/workspace-files/download?path=${encodeURIComponent(f.path)}`}
                      download={f.name}
                      title={t('Tải về')}
                      aria-label={t('Tải về')}
                      className="rounded p-1.5 text-muted hover:bg-panel hover:text-fg"
                    >
                      <Download className="size-3.5" />
                    </a>
                    {!f.readonly && !f.is_system && (
                      <button
                        onClick={() => {
                          if (confirm(t('Xóa tệp "{name}" khỏi workspace?', { name: f.name }))) {
                            del.mutate(f.path)
                          }
                        }}
                        title={t('Xóa')}
                        aria-label={t('Xóa')}
                        className="rounded p-1.5 text-muted hover:bg-panel hover:text-bad"
                      >
                        <Trash2 className="size-3.5" />
                      </button>
                    )}
                  </div>
                </div>
    )
  }
  const renderNode = (n: TreeNode, depth: number): React.ReactNode => [
    ...n.folders.map((d) => {
      const isClosed = !opened.has(d.path)
      const FIcon = isClosed ? Folder : FolderOpen
      return (
        <div key={`d:${d.path}`}>
          <button type="button" onClick={() => toggle(d.path)} aria-expanded={!isClosed}
            className="flex w-full items-center gap-2 py-2 pr-5 text-left transition hover:bg-panel2/50" style={{ paddingLeft: 20 + depth * 18 }}>
            <ChevronRight className={`size-3.5 shrink-0 text-muted transition ${isClosed ? '' : 'rotate-90'}`} />
            <FIcon className="size-4 shrink-0 text-accent" />
            <span className="truncate font-mono text-xs font-semibold">{d.name}</span>
            {d.path.split('/')[0] === 'skills' && <Badge>{t('Chỉ xem')}</Badge>}
            <span className="ml-auto text-[11px] text-muted">{t('{n} tệp', { n: d.count })}</span>
          </button>
          {!isClosed && <div className="divide-y divide-line border-t border-line">{renderNode(d, depth + 1)}</div>}
        </div>
      )
    }),
    ...n.files.map((f) => renderFile(f, depth)),
  ]

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title={t('Tất cả tệp trong không gian làm việc')}
          hint={t('Bao gồm các script, file báo cáo, bảng dữ liệu hoặc kết quả do Agent tạo ra trong quá trình làm việc.')}
          action={<span className="text-xs text-muted">{t('{n} tệp', { n: files.length })}</span>}
        />
        {files.length === 0 ? (
          <p className="p-8 text-center text-sm text-muted">{t('Chưa có tệp nào trong không gian làm việc.')}</p>
        ) : (
          <div className="divide-y divide-line">
            {renderNode(tree, 0)}
          </div>
        )}
      </Card>

      {/* Modal Preview */}
      {viewingFile && (
        <Modal
          open={!!viewingFile}
          onClose={() => setViewingFile(null)}
          wide
          title={viewingFile.path}
          footer={
            <div className="flex justify-between w-full">
              <a
                href={`/api/workspace-files/download?path=${encodeURIComponent(viewingFile.path)}`}
                download={viewingFile.name}
                className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-xs font-medium hover:bg-panel2"
              >
                <Download className="size-3.5" />
                {t('Tải về')}
              </a>
              <Button onClick={() => setViewingFile(null)}>{t('Đóng')}</Button>
            </div>
          }
        >
          {loadingPreview ? (
            <Loading />
          ) : (
            <pre className="max-h-[60vh] overflow-auto rounded-lg bg-bg p-4 font-mono text-xs leading-relaxed text-fg whitespace-pre-wrap break-words">
              {previewContent}
            </pre>
          )}
        </Modal>
      )}
    </div>
  )
}

export function WorkspacePage() {
  const [tab, setTab] = useState<string>('SOUL.md')
  const f = FILES.find((x) => x.id === tab)
  const tabs = [
    ...FILES.map((x) => ({ id: x.id, label: x.label })),
    { id: 'all_files', label: t('Tệp đã tạo') },
  ]

  return (
    <Page>
      <PageHeader title={t('Không gian làm việc')} />
      <Tabs value={tab} onChange={setTab} tabs={tabs} />
      <div className="mt-5">
        {tab === 'all_files' ? (
          <WorkspaceFilesBrowser />
        ) : f ? (
          <Editor key={f.id} file={f.id} />
        ) : null}
      </div>
    </Page>
  )
}
