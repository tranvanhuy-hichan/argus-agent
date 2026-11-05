import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowUpFromLine, GitBranch, GitCommitHorizontal, ShieldAlert } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import { t } from '@/lib/i18n.ts'
import type { GitStatus } from '@/lib/types'
import { cn, errMsg } from '@/lib/utils'

const STATUS_TONE = { new: 'text-ok', modified: 'text-warn', deleted: 'text-bad' } as const

/** Bảng git nằm trong popover của chip Lập trình: tạo nhánh, commit các file chọn, push (luôn cần xác nhận). Không bao giờ force push. */
export function GitPanel({ sid, tick }: { sid: string; tick: number }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [msg, setMsg] = useState('')
  const [branch, setBranch] = useState('')
  const [skip, setSkip] = useState<Set<string>>(new Set())
  const [confirmPush, setConfirmPush] = useState(false)
  const [allowMain, setAllowMain] = useState(false)
  const st = useQuery({ queryKey: ['git', sid, tick], queryFn: () => api.get<GitStatus>(`/api/sessions/${sid}/git`), refetchInterval: 5000 })

  const refresh = () => { void qc.invalidateQueries({ queryKey: ['git', sid] }) }
  const run = useMutation({
    mutationFn: ({ path, body }: { path: string; body: object }) => api.post<Record<string, string>>(`/api/sessions/${sid}/git/${path}`, body),
    onError: (e) => toast(errMsg(e), 'bad'),
  })

  const g = st.data
  if (!g?.repo) return null
  const files = g.files
  const picked = files.filter((f) => !skip.has(f.path)).map((f) => f.path)
  const suggested = `feat/${new Date().toISOString().slice(5, 10).replace('-', '')}-`
  const mainWarn = g.protected && !allowMain

  const createBranch = () => run.mutate({ path: 'branch', body: { name: branch.trim() } }, { onSuccess: (r) => { toast(t('Đã chuyển sang nhánh {name}', { name: r.branch })); setBranch(''); refresh() } })
  const commit = () => run.mutate({ path: 'commit', body: { message: msg, files: picked, allow_protected: allowMain } }, { onSuccess: (r) => { toast(t('Đã commit {id}', { id: r.commit })); setMsg(''); refresh() } })
  const push = () => run.mutate({ path: 'push', body: { confirm: true, allow_protected: allowMain } }, { onSuccess: () => { toast(t('Đã push nhánh {name}', { name: g.branch })); setConfirmPush(false); refresh() } })

  return (
    <div className="space-y-3 text-sm">
      <p className="flex items-center gap-1.5 text-xs text-muted"><GitBranch className="size-3.5" /><span className="font-mono text-fg">{g.branch}</span>{!!g.ahead && <span className="text-ok">↑{g.ahead}</span>}</p>
          {g.protected && (
            <div className="space-y-2 rounded-lg border border-warn/40 bg-warn/5 p-2.5">
              <p className="flex items-start gap-1.5 text-xs"><ShieldAlert className="mt-0.5 size-3.5 shrink-0 text-warn" />{t('Bạn đang ở nhánh {name}. Nên tạo nhánh mới trước khi commit.', { name: g.branch })}</p>
              <form className="flex gap-1.5" onSubmit={(e) => { e.preventDefault(); if (branch.trim()) createBranch() }}>
                <input value={branch} onChange={(e) => setBranch(e.target.value)} onFocus={() => !branch && setBranch(suggested)} placeholder={suggested + 'ten-viec'} className="min-w-0 flex-1 rounded-md border border-line bg-bg px-2 py-1 font-mono text-xs outline-none focus:border-accent" />
                <Button size="sm" type="submit" variant="primary" disabled={!branch.trim()} loading={run.isPending && run.variables?.path === 'branch'}>{t('Tạo nhánh')}</Button>
              </form>
              <label className="flex items-center gap-1.5 text-[11px] text-muted"><input type="checkbox" checked={allowMain} onChange={(e) => setAllowMain(e.target.checked)} />{t('Tôi biết, cho phép commit/push thẳng lên {name}', { name: g.branch })}</label>
            </div>
          )}
          <div>
            <p className="mb-1 flex items-center justify-between text-xs font-medium text-muted"><span>{t('Thay đổi chưa commit')}</span>{files.length > 0 && <button className="text-accent" onClick={() => setSkip(skip.size ? new Set() : new Set(files.map((f) => f.path)))}>{skip.size ? t('Chọn tất cả') : t('Bỏ chọn')}</button>}</p>
            {files.length === 0 ? <p className="text-xs text-muted">{t('Không có thay đổi nào.')}</p> : (
              <ul className="max-h-40 space-y-0.5 overflow-y-auto">
                {files.map((f) => (
                  <li key={f.path}><label className="flex cursor-pointer items-center gap-2 rounded px-1 py-0.5 font-mono text-xs hover:bg-panel2">
                    <input type="checkbox" checked={!skip.has(f.path)} onChange={() => setSkip((s) => { const n = new Set(s); if (n.has(f.path)) n.delete(f.path); else n.add(f.path); return n })} />
                    <span className={cn('w-3 shrink-0 text-center font-bold', STATUS_TONE[f.status])}>{f.status === 'new' ? 'A' : f.status === 'deleted' ? 'D' : 'M'}</span>
                    <span className="min-w-0 flex-1 truncate" title={f.path}>{f.path}</span>
                  </label></li>
                ))}
              </ul>
            )}
          </div>
          {files.length > 0 && (
            <form className="space-y-1.5" onSubmit={(e) => { e.preventDefault(); if (msg.trim() && picked.length && !mainWarn) commit() }}>
              <textarea value={msg} onChange={(e) => setMsg(e.target.value)} rows={2} placeholder={t('Nội dung commit, ví dụ: feat: thêm công tắc Lập trình')} className="w-full resize-none rounded-md border border-line bg-bg px-2 py-1.5 text-xs outline-none focus:border-accent" />
              <Button size="sm" type="submit" variant="primary" className="w-full" disabled={!msg.trim() || !picked.length || mainWarn} loading={run.isPending && run.variables?.path === 'commit'}>
                <GitCommitHorizontal className="size-3.5" />{t('Commit {n} file', { n: picked.length })}
              </Button>
            </form>
          )}
          <div className="border-t border-line pt-2.5">
            {!confirmPush ? (
              <Button size="sm" className="w-full" disabled={mainWarn} onClick={() => setConfirmPush(true)}><ArrowUpFromLine className="size-3.5" />{g.upstream ? t('Push lên {up}', { up: g.upstream }) : t('Push nhánh {name} lên origin', { name: g.branch })}{!!g.ahead && ` (↑${g.ahead})`}</Button>
            ) : (
              <div className="space-y-1.5 rounded-lg border border-warn/40 bg-warn/5 p-2.5">
                <p className="text-xs">{t('Đẩy nhánh {name} lên origin? Hành động này công khai code của bạn lên máy chủ.', { name: g.branch })}</p>
                <div className="flex gap-1.5"><Button size="sm" variant="primary" onClick={push} loading={run.isPending && run.variables?.path === 'push'}>{t('Xác nhận push')}</Button><Button size="sm" onClick={() => setConfirmPush(false)}>{t('Hủy')}</Button></div>
              </div>
            )}
            <p className="mt-1.5 text-[11px] text-muted">{t('Không bao giờ force push. Push luôn cần bạn xác nhận.')}</p>
          </div>
    </div>
  )
}
