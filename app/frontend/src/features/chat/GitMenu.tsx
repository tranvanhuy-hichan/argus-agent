import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowUpFromLine, Check, GitBranch, Plus, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Select } from '@/components/ui/Form'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import { t } from '@/lib/i18n.ts'
import type { GitStatus } from '@/lib/types'
import { cn, errMsg } from '@/lib/utils'

const STATUS_TONE = { new: 'text-ok', modified: 'text-warn', deleted: 'text-bad' } as const
const slug = (s: string) => s.toLowerCase().replace(/^[a-z]+(\(.*?\))?:\s*/, '').replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 30)

/** Bảng git trong popover của chip Lập trình: chọn/tạo nhánh, chọn file, commit (có gợi ý), push. Không bao giờ force push. */
export function GitPanel({ sid, tick }: { sid: string; tick: number }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [msg, setMsg] = useState('')
  const [newBranch, setNewBranch] = useState('')
  const [creating, setCreating] = useState(false)
  const [branchName, setBranchName] = useState('')
  const [skip, setSkip] = useState<Set<string>>(new Set())
  const [confirmPush, setConfirmPush] = useState(false)
  const [direct, setDirect] = useState(false)
  const st = useQuery({ queryKey: ['git', sid, tick], queryFn: () => api.get<GitStatus>(`/api/sessions/${sid}/git`), refetchInterval: 5000 })
  const br = useQuery({ queryKey: ['git-branches', sid, st.data?.branch], queryFn: () => api.get<{ current: string; branches: string[] }>(`/api/sessions/${sid}/git/branches`), enabled: !!st.data?.repo })
  const refresh = () => { void qc.invalidateQueries({ queryKey: ['git', sid] }); void qc.invalidateQueries({ queryKey: ['git-branches', sid] }) }
  const run = useMutation({
    mutationFn: ({ path, body }: { path: string; body: object }) => api.post<Record<string, string>>(`/api/sessions/${sid}/git/${path}`, body),
    onError: (e) => toast(errMsg(e), 'bad'),
  })
  const busy = (p: string) => run.isPending && run.variables?.path === p

  const g = st.data
  if (!g?.repo) return <p className="text-xs text-muted">{t('Thư mục này chưa phải kho git (chạy git init để dùng commit/push).')}</p>
  const files = g.files
  const picked = files.filter((f) => !skip.has(f.path)).map((f) => f.path)
  const onMain = !!g.protected && !direct
  const branches = br.data?.branches ?? [g.branch]
  const target = newBranch || `feat/${slug(msg) || new Date().toISOString().slice(5, 10).replace('-', '')}`

  const switchTo = (name: string) => run.mutate({ path: 'switch', body: { name } }, { onSuccess: () => { toast(t('Đã chuyển sang nhánh {name}', { name })); refresh() } })
  const createBranch = () => run.mutate({ path: 'branch', body: { name: branchName.trim() } }, { onSuccess: (r) => { toast(t('Đã tạo và chuyển sang nhánh {name}', { name: r.branch })); setCreating(false); setBranchName(''); refresh() } })
  const suggest = () => run.mutate({ path: 'suggest', body: { files: picked } }, { onSuccess: (r) => setMsg(r.message) })
  const commit = () => run.mutate({ path: 'commit', body: { message: msg, files: picked, allow_protected: direct, new_branch: onMain ? target : '' } },
    { onSuccess: (r) => { toast(t('Đã commit {id} trên nhánh {name}', { id: r.commit, name: r.branch })); setMsg(''); setNewBranch(''); refresh() } })
  const push = () => run.mutate({ path: 'push', body: { confirm: true, allow_protected: direct } }, { onSuccess: () => { toast(t('Đã push nhánh {name}', { name: g.branch })); setConfirmPush(false); refresh() } })

  return (
    <div className="space-y-3 text-sm">
      {/* 1. Nhanh */}
      <div>
        <p className="mb-1 text-xs font-medium text-muted">{t('Nhánh')}</p>
        <div className="flex gap-1.5">
          <Select value={g.branch} onChange={(e) => e.target.value !== g.branch && switchTo(e.target.value)} className="min-w-0 flex-1 font-mono text-xs" aria-label={t('Chuyển nhánh')}>
            {branches.map((b) => <option key={b} value={b}>{b}</option>)}
          </Select>
          <Button size="sm" onClick={() => setCreating((c) => !c)} aria-expanded={creating}><Plus className="size-3.5" />{t('Nhánh mới')}</Button>
        </div>
        {creating && (
          <form className="mt-1.5 flex gap-1.5" onSubmit={(e) => { e.preventDefault(); if (branchName.trim()) createBranch() }}>
            <input autoFocus value={branchName} onChange={(e) => setBranchName(e.target.value)} placeholder="feat/ten-viec" className="min-w-0 flex-1 rounded-md border border-line bg-bg px-2 py-1 font-mono text-xs outline-none focus:border-accent" />
            <Button size="sm" type="submit" variant="primary" disabled={!branchName.trim()} loading={busy('branch')}>{t('Tạo')}</Button>
          </form>
        )}
        {g.protected && !direct && <p className="mt-1 text-[11px] text-warn">{t('Đây là nhánh chính: commit sẽ tự tạo nhánh mới để an toàn.')}</p>}
      </div>

      {/* 2. Thay doi + commit */}
      <div className="border-t border-line pt-3">
        <p className="mb-1 flex items-center justify-between text-xs font-medium text-muted"><span>{t('Thay đổi chưa commit')} ({files.length})</span>{files.length > 0 && <button className="text-accent" onClick={() => setSkip(skip.size ? new Set() : new Set(files.map((f) => f.path)))}>{skip.size ? t('Chọn tất cả') : t('Bỏ chọn')}</button>}</p>
        {files.length === 0 ? <p className="flex items-center gap-1 text-xs text-muted"><Check className="size-3.5 text-ok" />{t('Không có gì để commit.')}</p> : (
          <>
            <ul className="max-h-36 space-y-0.5 overflow-y-auto">
              {files.map((f) => (
                <li key={f.path}><label className="flex cursor-pointer items-center gap-2 rounded px-1 py-0.5 font-mono text-xs hover:bg-panel2">
                  <input type="checkbox" checked={!skip.has(f.path)} onChange={() => setSkip((s) => { const n = new Set(s); if (n.has(f.path)) n.delete(f.path); else n.add(f.path); return n })} />
                  <span className={cn('w-3 shrink-0 text-center font-bold', STATUS_TONE[f.status])}>{f.status === 'new' ? 'A' : f.status === 'deleted' ? 'D' : 'M'}</span>
                  <span className="min-w-0 flex-1 truncate" title={f.path}>{f.path}</span>
                </label></li>
              ))}
            </ul>
            <form className="mt-2 space-y-1.5" onSubmit={(e) => { e.preventDefault(); if (msg.trim() && picked.length) commit() }}>
              <div className="relative">
                <textarea value={msg} onChange={(e) => setMsg(e.target.value)} rows={2} placeholder={t('Nội dung commit (bấm ✨ để tự gợi ý)')} className="w-full resize-none rounded-md border border-line bg-bg py-1.5 pl-2 pr-8 text-xs outline-none focus:border-accent" />
                <button type="button" onClick={suggest} disabled={!picked.length || busy('suggest')} title={t('Gợi ý nội dung commit')} className="absolute right-1.5 top-1.5 rounded p-1 text-accent hover:bg-panel2 disabled:opacity-40"><Sparkles className={cn('size-3.5', busy('suggest') && 'animate-pulse')} /></button>
              </div>
              {onMain && <label className="flex items-center gap-1.5 text-xs text-muted"><GitBranch className="size-3.5 shrink-0" />{t('Nhánh mới:')}<input value={newBranch || target} onChange={(e) => setNewBranch(e.target.value)} className="min-w-0 flex-1 rounded border border-line bg-bg px-1.5 py-0.5 font-mono text-xs text-fg outline-none focus:border-accent" /></label>}
              <Button size="sm" type="submit" variant="primary" className="w-full" disabled={!msg.trim() || !picked.length} loading={busy('commit')}>
                {onMain ? t('Tạo nhánh và commit {n} file', { n: picked.length }) : t('Commit {n} file', { n: picked.length })}
              </Button>
            </form>
          </>
        )}
      </div>

      {/* 3. Push */}
      <div className="border-t border-line pt-3">
        {!confirmPush ? (
          <Button size="sm" className="w-full" disabled={onMain} onClick={() => setConfirmPush(true)} title={onMain ? t('Hãy chuyển sang một nhánh khác để push') : undefined}>
            <ArrowUpFromLine className="size-3.5" />{g.upstream ? t('Push lên {up}', { up: g.upstream }) : t('Push nhánh {name} lên origin', { name: g.branch })}{!!g.ahead && ` (↑${g.ahead})`}
          </Button>
        ) : (
          <div className="space-y-1.5 rounded-lg border border-warn/40 bg-warn/5 p-2.5">
            <p className="text-xs">{t('Đẩy nhánh {name} lên origin? Code sẽ được gửi lên máy chủ.', { name: g.branch })}</p>
            <div className="flex gap-1.5"><Button size="sm" variant="primary" onClick={push} loading={busy('push')}>{t('Xác nhận push')}</Button><Button size="sm" onClick={() => setConfirmPush(false)}>{t('Hủy')}</Button></div>
          </div>
        )}
        {g.protected && <label className="mt-1.5 flex items-center gap-1.5 text-[11px] text-muted"><input type="checkbox" checked={direct} onChange={(e) => { setDirect(e.target.checked); setConfirmPush(false) }} />{t('Nâng cao: cho phép commit/push thẳng lên {name}', { name: g.branch })}</label>}
      </div>
    </div>
  )
}
