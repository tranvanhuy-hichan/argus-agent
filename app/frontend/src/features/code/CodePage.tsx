import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowUp, Clock, Folder, FolderGit2, FolderOpen, GitBranch, Home } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { Input } from '@/components/ui/Form'
import { Loading, Page, PageHeader } from '@/components/ui/misc'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import { t } from '@/lib/i18n.ts'
import type { BrowseResult, RecentProject } from '@/lib/types'
import { errMsg, timeAgo } from '@/lib/utils'

const shorten = (p: string) => p.replace(/^\/home\/[^/]+/, '~')

/** Chế độ Code: chọn một thư mục dự án bất kỳ trên máy để agent làm việc trực tiếp trong đó. */
export function CodePage() {
  const nav = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [path, setPath] = useState('')
  const [dir, setDir] = useState('')
  const recent = useQuery({ queryKey: ['code-recent'], queryFn: () => api.get<RecentProject[]>('/api/code/projects') })
  const browse = useQuery({ queryKey: ['code-browse', dir], queryFn: () => api.get<BrowseResult>(`/api/code/browse?path=${encodeURIComponent(dir)}`), retry: false })
  const open = useMutation({
    mutationFn: (p: string) => api.post<{ id: string }>('/api/code/open', { path: p }),
    onSuccess: async (r) => {
      await qc.invalidateQueries({ queryKey: ['sessions'] })
      nav(`/code/${r.id}`)
    },
    onError: (e) => toast(errMsg(e), 'bad'),
  })
  const b = browse.data

  return (
    <Page>
      <PageHeader title={t('Lập trình')} />
      <div className="grid items-start gap-4 lg:grid-cols-2">
        <div className="space-y-4">
          <Card>
            <CardHeader title={t('Mở dự án')} />
            <form className="flex gap-2 p-5" onSubmit={(e) => { e.preventDefault(); if (path.trim()) open.mutate(path.trim()) }}>
              <Input value={path} onChange={(e) => setPath(e.target.value)} placeholder={t('Dán đường dẫn thư mục, ví dụ ~/Projects/my-app')} aria-label={t('Đường dẫn dự án')} className="font-mono" />
              <Button type="submit" variant="primary" loading={open.isPending && open.variables === path.trim()} disabled={!path.trim()}><FolderOpen className="size-4" />{t('Mở')}</Button>
            </form>
          </Card>
          <Card>
            <CardHeader title={t('Dự án gần đây')} />
            {recent.isLoading ? <Loading /> : !recent.data?.length ? <p className="p-5 text-sm text-muted">{t('Chưa mở dự án nào. Chọn một thư mục ở bên cạnh hoặc dán đường dẫn.')}</p> : (
              <div className="grid gap-3 p-4 sm:grid-cols-2">
                {recent.data.map((p) => (
                  <button key={p.path} onClick={() => open.mutate(p.path)} className="group flex flex-col gap-3 rounded-xl border border-line bg-bg p-4 text-left transition hover:border-accent/60">
                    <span className="flex items-start justify-between gap-2">
                      <span className="grid size-10 place-items-center rounded-lg bg-accent/12 text-accent"><FolderGit2 className="size-5" /></span>
                      {p.branch && <span className="flex items-center gap-1 rounded-md bg-panel2 px-2 py-0.5 font-mono text-[11px] text-muted"><GitBranch className="size-3" />{p.branch}</span>}
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate font-semibold">{p.name}</span>
                      <span className="mt-0.5 block truncate font-mono text-xs text-muted" title={p.path}>{shorten(p.path)}</span>
                    </span>
                    <span className="flex items-center gap-1 text-xs text-muted"><Clock className="size-3" />{timeAgo(p.ts)}</span>
                  </button>
                ))}
              </div>
            )}
          </Card>
        </div>

        <Card>
          <CardHeader title={t('Chọn thư mục')} action={b && <Button size="sm" variant="primary" onClick={() => open.mutate(b.path)} loading={open.isPending && open.variables === b.path}><FolderOpen className="size-3.5" />{t('Mở thư mục này')}</Button>} />
          <div className="flex items-center gap-1 border-b border-line px-5 py-2 text-xs text-muted">
            <button onClick={() => setDir('')} aria-label={t('Thư mục nhà')} className="rounded p-1 hover:bg-panel2 hover:text-fg"><Home className="size-3.5" /></button>
            {b?.parent && <button onClick={() => setDir(b.parent!)} aria-label={t('Lên một cấp')} className="rounded p-1 hover:bg-panel2 hover:text-fg"><ArrowUp className="size-3.5" /></button>}
            <span className="ml-1 min-w-0 flex-1 truncate font-mono" title={b?.path}>{b ? shorten(b.path) : ''}</span>
            {b?.git && <Badge tone="ok">git</Badge>}
          </div>
          {browse.isLoading ? <Loading /> : browse.error ? <p className="p-5 text-sm text-bad">{errMsg(browse.error)}</p> : !b?.dirs.length ? <p className="p-5 text-sm text-muted">{t('Thư mục này không có thư mục con.')}</p> : (
            <ul className="grid max-h-[30rem] grid-cols-2 gap-2 overflow-y-auto p-3 sm:grid-cols-3">
              {b.dirs.map((d) => (
                <li key={d.path}>
                  <button onClick={() => setDir(d.path)} onDoubleClick={() => open.mutate(d.path)} title={d.path}
                    className="flex h-full w-full flex-col items-start gap-2 rounded-lg border border-line bg-bg p-3 text-left transition hover:border-accent/60">
                    {d.git ? <FolderGit2 className="size-6 text-accent" /> : <Folder className="size-6 text-muted" />}
                    <span className="w-full truncate text-sm font-medium">{d.name}</span>
                    {d.git && <Badge tone="ok">git</Badge>}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </Page>
  )
}
