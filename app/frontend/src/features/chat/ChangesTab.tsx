import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, FilePlus2, FileX2, GitBranch, Pencil, Undo2 } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Loading } from '@/components/ui/misc'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import { t } from '@/lib/i18n.ts'
import type { GitFile, GitStatus } from '@/lib/types'
import { cn, errMsg } from '@/lib/utils'

const ICON = { new: FilePlus2, modified: Pencil, deleted: FileX2 }
const TONE = { new: 'text-ok', modified: 'text-warn', deleted: 'text-bad' }

export function Diff({ sid, file, onBack, onReverted }: { sid: string; file: GitFile; onBack: () => void; onReverted: () => void }) {
  const toast = useToast()
  const q = useQuery({ queryKey: ['git-diff', sid, file.path], queryFn: () => api.get<{ diff: string; truncated: boolean }>(`/api/sessions/${sid}/git/diff?path=${encodeURIComponent(file.path)}`) })
  const revert = useMutation({
    mutationFn: () => api.post(`/api/sessions/${sid}/git/revert`, { path: file.path }),
    onSuccess: () => { toast(t('Đã hoàn tác')); onReverted() },
    onError: (e) => toast(errMsg(e), 'bad'),
  })
  const lines = (q.data?.diff ?? '').split('\n')
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-line px-3 py-2">
        <button onClick={onBack} aria-label={t('Quay lại')} className="rounded p-1 text-muted hover:bg-panel2 hover:text-fg"><ArrowLeft className="size-4" /></button>
        <span className="min-w-0 flex-1 truncate font-mono text-xs">{file.path}</span>
        <Button size="sm" variant="danger" loading={revert.isPending} onClick={() => { if (confirm(file.status === 'new' ? t('Xóa file mới này?') : t('Hoàn tác file này về bản gốc?'))) revert.mutate() }}><Undo2 className="size-3.5" />{t('Hoàn tác')}</Button>
      </div>
      <div className="min-h-0 flex-1 overflow-auto bg-bg py-2 font-mono text-[12px] leading-[1.55]">
        {q.isLoading ? <Loading /> : !q.data?.diff ? <p className="p-6 text-center text-sm text-muted">{t('Không có thay đổi để hiển thị (file nhị phân hoặc rỗng).')}</p> : lines.map((l, i) => (
          <div key={i} className={cn('whitespace-pre px-3', l.startsWith('+') && !l.startsWith('+++') && 'bg-ok/10 text-ok', l.startsWith('-') && !l.startsWith('---') && 'bg-bad/10 text-bad', l.startsWith('@@') && 'text-info', /^(diff|index|---|\+\+\+|new file|deleted file)/.test(l) && 'text-muted')}>{l || ' '}</div>
        ))}
        {q.data?.truncated && <p className="px-3 pt-2 text-muted">{t('… diff quá dài, đã cắt bớt.')}</p>}
      </div>
    </div>
  )
}

/** Thay đổi trong dự án (git): xem diff từng file, hoàn tác file agent đã sửa. */
export function ChangesTab({ sid, filesTick }: { sid: string | null; filesTick: number }) {
  const qc = useQueryClient()
  const [open, setOpen] = useState<GitFile | null>(null)
  const q = useQuery({ queryKey: ['git', sid, filesTick], queryFn: () => api.get<GitStatus>(`/api/sessions/${sid}/git`), enabled: !!sid, refetchInterval: 8000 })
  if (!sid) return <p className="p-6 text-center text-sm text-muted">{t('Mở một dự án ở mục Lập trình để xem thay đổi.')}</p>
  if (q.isLoading) return <Loading />
  if (q.error) return <p className="p-6 text-center text-sm text-bad">{errMsg(q.error)}</p>
  const g = q.data!
  if (!g.repo) return <p className="p-6 text-center text-sm text-muted">{t('Dự án này chưa dùng git nên không xem được thay đổi. Chạy “git init” trong thư mục dự án để bật.')}</p>
  if (open) return <Diff sid={sid} file={open} onBack={() => setOpen(null)} onReverted={() => { setOpen(null); void qc.invalidateQueries({ queryKey: ['git', sid] }); void qc.invalidateQueries({ queryKey: ['files', sid] }) }} />
  return (
    <div>
      <p className="flex items-center gap-1.5 border-b border-line px-3 py-2.5 text-xs text-muted"><GitBranch className="size-3.5" /><span className="font-mono">{g.branch || 'HEAD'}</span><span className="ml-auto">{t('{n} file thay đổi', { n: g.files.length })}</span></p>
      {g.files.length === 0 ? <p className="p-6 text-center text-sm text-muted">{t('Chưa có thay đổi nào. Khi agent sửa code, các file sẽ hiện ở đây kèm diff.')}</p> : (
        <ul className="p-2">
          {g.files.map((f) => {
            const Icon = ICON[f.status]
            return (
              <li key={f.path}>
                <button onClick={() => setOpen(f)} className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition hover:bg-panel2">
                  <Icon className={cn('size-4 shrink-0', TONE[f.status])} /><span className="min-w-0 flex-1 truncate font-mono text-[13px]">{f.path}</span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
