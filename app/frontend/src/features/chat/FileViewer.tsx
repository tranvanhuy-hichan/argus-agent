import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Download, ExternalLink, Save, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Loading } from '@/components/ui/misc'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import { t } from '@/lib/i18n.ts'
import { errMsg } from '@/lib/utils'
import { Markdown } from './Markdown'

const IMG = /\.(png|jpe?g|gif|webp|svg|bmp)$/i
const rawUrl = (sid: string, path: string) => `/api/sessions/${sid}/file?path=${encodeURIComponent(path)}&raw=true`

export function FileViewer({ sid, path, onBack }: { sid: string; path: string; onBack: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const isImg = IMG.test(path)
  const isHtml = /\.html?$/i.test(path)
  const q = useQuery({ queryKey: ['file', sid, path], queryFn: () => api.get<{ binary: boolean; size: number; truncated?: boolean; content: string }>(`/api/sessions/${sid}/file?path=${encodeURIComponent(path)}`), enabled: !isImg })
  const [text, setText] = useState('')
  const [preview, setPreview] = useState(true)
  useEffect(() => { if (q.data) setText(q.data.content) }, [q.data])
  const refreshTree = () => { void qc.invalidateQueries({ queryKey: ['files', sid] }) }
  const save = useMutation({ mutationFn: () => api.put(`/api/sessions/${sid}/file`, { path, content: text }), onSuccess: () => { toast(t('Đã lưu')); void qc.invalidateQueries({ queryKey: ['file', sid, path] }) }, onError: (e) => toast(errMsg(e), 'bad') })
  const del = useMutation({ mutationFn: () => api.del(`/api/sessions/${sid}/file?path=${encodeURIComponent(path)}`), onSuccess: () => { refreshTree(); onBack() } })
  const isMd = /\.md$/i.test(path)

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center gap-1.5 border-b border-line px-3 py-2">
        <button onClick={onBack} aria-label={t('Quay lại danh sách')} className="rounded p-1 text-muted hover:bg-panel2 hover:text-fg"><ArrowLeft className="size-4" /></button>
        <span className="min-w-0 flex-1 truncate font-mono text-xs" title={path}>{path}</span>
        {(isHtml || isMd) && <button onClick={() => setPreview(!preview)} className="rounded border border-line px-2 py-0.5 text-[11px] text-muted hover:text-fg">{preview ? t('Mã nguồn') : t('Xem trước')}</button>}
        <a href={rawUrl(sid, path)} download={path.split('/').pop()} aria-label={t('Tải xuống')} className="rounded p-1 text-muted hover:bg-panel2 hover:text-fg"><Download className="size-4" /></a>
        <a href={rawUrl(sid, path)} target="_blank" rel="noreferrer noopener" aria-label={t('Mở trong tab mới')} className="rounded p-1 text-muted hover:bg-panel2 hover:text-fg"><ExternalLink className="size-4" /></a>
        <button onClick={() => { if (confirm(t('Xóa {path}?', { path }))) del.mutate() }} aria-label={t('Xóa file')} className="rounded p-1 text-muted hover:bg-panel2 hover:text-bad"><Trash2 className="size-4" /></button>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        {isImg ? (
          <div className="grid min-h-full place-items-center bg-bg p-4"><img src={rawUrl(sid, path)} alt={path} className="max-h-full max-w-full rounded-lg border border-line" /></div>
        ) : q.isLoading ? <Loading /> : q.data?.binary ? (
          <p className="p-6 text-center text-sm text-muted">{t('File nhị phân ({size} KB). Dùng nút tải xuống để mở.', { size: (q.data.size / 1024).toFixed(1) })}</p>
        ) : isHtml && preview ? (
          <iframe title={path} src={rawUrl(sid, path)} sandbox="" className="size-full bg-white" />
        ) : isMd && preview ? (
          <div className="p-4 text-sm"><Markdown text={text} /></div>
        ) : (
          <textarea value={text} onChange={(e) => setText(e.target.value)} spellCheck={false} aria-label={t('Nội dung {path}', { path })} className="size-full resize-none bg-bg p-3 font-mono text-[12.5px] leading-relaxed focus:outline-none" />
        )}
      </div>
      {!isImg && q.data && !q.data.binary && (
        <div className="flex items-center gap-2 border-t border-line px-3 py-2">
          <Button size="sm" variant="primary" loading={save.isPending} disabled={text === q.data.content || q.data.truncated} onClick={() => save.mutate()}><Save className="size-3.5" />{t('Lưu')}</Button>
          <span className="text-[11px] text-muted">{(q.data.size / 1024).toFixed(1)} KB{q.data.truncated ? t(' · file lớn, chỉ xem') : ''}</span>
        </div>
      )}
    </div>
  )
}
