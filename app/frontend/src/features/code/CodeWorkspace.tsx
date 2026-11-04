import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, FileCode, FolderTree, GitBranch, GitCompare, House, LoaderCircle, PanelBottom, Save, X } from 'lucide-react'
import { AgentMark } from '@/components/ui/AgentMark'
import { Button } from '@/components/ui/Button'
import { Loading } from '@/components/ui/misc'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import { t, tk } from '@/lib/i18n.ts'
import { useConfig, useMcp, useSkills } from '@/lib/queries'
import type { FileEntry, GitFile, GitStatus } from '@/lib/types'
import { cn, errMsg } from '@/lib/utils'
import { mcpBrand } from '@/features/integrations/brands'
import { Diff } from '@/features/chat/ChangesTab'
import { Composer } from '@/features/chat/Composer'
import { MessageView } from '@/features/chat/MessageView'
import { PlanCard } from '@/features/chat/PlanCard'
import { SessionContext } from '@/features/chat/session'
import { TerminalTab } from '@/features/chat/TerminalTab'
import type { Effort, Permission } from '@/features/chat/permissions'
import { useChat } from '@/features/chat/useChat'
import { CodeEditor } from './CodeEditor'
import { ProjectTree } from './ProjectTree'

const store = {
  get: (k: string, d: string) => { try { return localStorage.getItem(k) ?? d } catch { return d } },
  set: (k: string, v: string) => { try { localStorage.setItem(k, v) } catch { /* che do rieng tu */ } },
}
function useMediaQuery(q: string) {
  const [m, setM] = useState(() => window.matchMedia(q).matches)
  useEffect(() => {
    const mq = window.matchMedia(q)
    const on = () => setM(mq.matches)
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [q])
  return m
}
const IMG = /\.(png|jpe?g|gif|webp|svg|ico|bmp)$/i
const IDEAS = [tk('Giải thích cấu trúc dự án này'), tk('Chạy test và sửa các lỗi nếu có'), tk('Tìm các lỗi tiềm ẩn trong code'), tk('Viết thêm test cho phần còn thiếu')]

type Tab = { key: string; path: string; kind: 'file' | 'diff'; status?: GitFile['status'] }

function FileTab({ sid, path, draft, onDraft, onSaved }: { sid: string; path: string; draft: string | undefined; onDraft: (v: string | undefined) => void; onSaved: () => void }) {
  const toast = useToast()
  const q = useQuery({ queryKey: ['file', sid, path], queryFn: () => api.get<{ binary: boolean; size: number; truncated?: boolean; content: string }>(`/api/sessions/${sid}/file?path=${encodeURIComponent(path)}`), enabled: !IMG.test(path) })
  const save = useMutation({
    mutationFn: (content: string) => api.put(`/api/sessions/${sid}/file`, { path, content }),
    onSuccess: () => { onDraft(undefined); onSaved(); toast(t('Đã lưu')) },
    onError: (e) => toast(errMsg(e), 'bad'),
  })
  if (IMG.test(path)) return <div className="grid size-full place-items-center overflow-auto bg-bg p-4"><img src={`/api/sessions/${sid}/file?path=${encodeURIComponent(path)}&raw=true`} alt={path} className="max-h-full max-w-full rounded border border-line" /></div>
  if (q.isLoading) return <Loading />
  if (q.data?.binary) return <p className="p-8 text-center text-sm text-muted">{t('File nhị phân ({size} KB), không xem được.', { size: (q.data.size / 1024).toFixed(1) })}</p>
  const value = draft ?? q.data?.content ?? ''
  const locked = !!q.data?.truncated
  return (
    <div className="flex size-full min-h-0 flex-col">
      <div className="min-h-0 flex-1"><CodeEditor value={value} onChange={(v) => onDraft(v === q.data?.content ? undefined : v)} path={path} readOnly={locked} onSave={() => draft !== undefined && !locked && save.mutate(draft)} /></div>
      {(draft !== undefined || locked) && (
        <div className="flex items-center gap-2 border-t border-line bg-panel px-3 py-1.5 text-xs text-muted">
          {locked ? t('File lớn, chỉ xem.') : <><Button size="sm" variant="primary" loading={save.isPending} onClick={() => save.mutate(draft!)}><Save className="size-3.5" />{t('Lưu')}</Button>{t('Có thay đổi chưa lưu (Ctrl+S)')}</>}
        </div>
      )}
    </div>
  )
}

/** Chế độ Code: giao diện kiểu IDE (cây thư mục, trình soạn thảo, terminal) với chat của agent ở bên phải. */
export function CodeWorkspace() {
  const { sid = '' } = useParams()
  const nav = useNavigate()
  const qc = useQueryClient()
  const chat = useChat()
  const cfg = useConfig()
  const skills = useSkills()
  const mcp = useMcp()
  const toast = useToast()
  const [pane, setPane] = useState<'files' | 'editor' | 'chat'>('chat') // màn hình hẹp chỉ hiện một khung
  const [side, setSide] = useState<'files' | 'changes'>('files')
  const [tabs, setTabs] = useState<Tab[]>([])
  const [active, setActive] = useState<string | null>(null)
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [terminal, setTerminal] = useState(() => store.get('code-terminal', '0') === '1')
  const [chatW, setChatW] = useState(() => Number(store.get('code-chat-w', '440')))
  const [text, setText] = useState('')
  const [provider, setProvider] = useState<string | null>(null)
  const [permission, setPermission] = useState<Permission>('default')
  const [effort, setEffort] = useState<Effort>('auto')
  const [attachments, setAttachments] = useState<string[]>([])
  const wide = useMediaQuery('(min-width: 768px)')
  const scroller = useRef<HTMLDivElement>(null)
  const stick = useRef(true)
  const drag = useRef(false)

  const info = useQuery({ queryKey: ['session', sid], queryFn: () => api.get<{ title: string; project?: string }>(`/api/sessions/${sid}`), retry: false })
  const files = useQuery({ queryKey: ['files', sid, chat.filesTick], queryFn: () => api.get<FileEntry[]>(`/api/sessions/${sid}/files`), enabled: !!info.data?.project })
  const git = useQuery({ queryKey: ['git', sid, chat.filesTick], queryFn: () => api.get<GitStatus>(`/api/sessions/${sid}/git`), enabled: !!info.data?.project, refetchInterval: 8000 })
  const changes = useMemo(() => new Map((git.data?.files ?? []).map((f) => [f.path, f.status] as const)), [git.data])

  useEffect(() => { if (sid) void chat.open(sid) }, [sid, chat.open]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { store.set('code-terminal', terminal ? '1' : '0') }, [terminal])
  useEffect(() => { store.set('code-chat-w', String(chatW)) }, [chatW])
  useEffect(() => { // agent vừa sửa file: nạp lại những file đang mở (trừ file đang có bản nháp)
    void qc.invalidateQueries({ queryKey: ['file', sid] })
  }, [chat.filesTick, qc, sid])
  useEffect(() => {
    const el = scroller.current
    if (el && stick.current) el.scrollTop = el.scrollHeight
  }, [chat.items, chat.status])
  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => { if (Object.keys(drafts).length) e.preventDefault() }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [drafts])

  const openTab = useCallback((path: string, kind: Tab['kind'] = 'file', status?: GitFile['status']) => {
    const key = `${kind}:${path}`
    setTabs((ts) => (ts.some((x) => x.key === key) ? ts : [...ts, { key, path, kind, status }]))
    setActive(key)
    setPane('editor')
  }, [])
  const closeTab = (key: string) => {
    const tab = tabs.find((x) => x.key === key)
    if (tab && tab.kind === 'file' && drafts[tab.path] !== undefined && !confirm(t('Đóng {path} mà chưa lưu?', { path: tab.path }))) return
    if (tab?.kind === 'file') setDrafts(({ [tab.path]: _, ...rest }) => rest)
    const left = tabs.filter((x) => x.key !== key)
    setTabs(left)
    if (active === key) setActive(left[left.length - 1]?.key ?? null)
  }

  if (info.error) return <div className="grid h-full place-items-center text-sm text-muted"><div className="text-center"><p>{errMsg(info.error)}</p><Link to="/code" className="mt-2 inline-block text-accent hover:underline">{t('Về danh sách dự án')}</Link></div></div>
  if (!info.data || !cfg.data) return <Loading />
  if (!info.data.project) { nav(`/chat?session=${sid}`, { replace: true }); return null }

  const project = info.data.project
  const providers = Object.keys(cfg.data.config.providers)
  const prov = provider ?? cfg.data.config.default_provider
  const activeTab = tabs.find((x) => x.key === active)
  const lastUser = [...chat.items].reverse().find((i) => i.kind === 'user')
  const lastAssistant = [...chat.items].reverse().find((i) => i.kind === 'assistant')
  const dirtyCount = Object.keys(drafts).length

  const submit = () => {
    if (!text.trim() || chat.busy) return
    stick.current = true
    void chat.send(text, prov, attachments, { permission, effort })
    setText('')
    setAttachments([])
  }
  const resend = async (override?: string) => {
    const last = await chat.rewindLast()
    if (!last) return
    stick.current = true
    void chat.send(override ?? last.text, prov, last.attachments)
  }
  const idea = (s: string) => { stick.current = true; void chat.send(s, prov) }
  const afterRevert = () => { void qc.invalidateQueries({ queryKey: ['git', sid] }); void qc.invalidateQueries({ queryKey: ['files', sid] }); void qc.invalidateQueries({ queryKey: ['file', sid] }) }

  return (
    <SessionContext.Provider value={sid}>
      <div className="flex h-full flex-col bg-bg">
        <header className="flex h-11 shrink-0 items-center gap-3 border-b border-line bg-panel px-3 text-sm">
          <Link to="/code" aria-label={t('Về danh sách dự án')} title={t('Về danh sách dự án')} className="rounded-md p-1.5 text-muted transition hover:bg-panel2 hover:text-fg"><ArrowLeft className="size-4" /></Link>
          <AgentMark size="sm" className="!mt-0 !size-6" />
          <span className="truncate font-medium" title={project}>{info.data.title}</span>
          {git.data?.repo && <span className="flex items-center gap-1 rounded-md bg-panel2 px-2 py-0.5 font-mono text-xs text-muted"><GitBranch className="size-3" />{git.data.branch || 'HEAD'}</span>}
          <span className="hidden truncate font-mono text-xs text-muted xl:block" title={project}>{project.replace(/^\/home\/[^/]+/, '~')}</span>
          <div className="ml-auto flex items-center gap-1">
            <div className="mr-1 flex rounded-md bg-panel2 p-0.5 md:hidden" role="tablist" aria-label={t('Khung hiển thị')}>
              {([['files', t('Tệp')], ['editor', t('Soạn thảo')], ['chat', 'Agent']] as const).map(([id, label]) => (
                <button key={id} role="tab" aria-selected={pane === id} onClick={() => setPane(id)} className={cn('rounded px-2 py-1 text-xs font-medium', pane === id ? 'bg-panel text-fg' : 'text-muted')}>{label}</button>
              ))}
            </div>
            <button onClick={() => setTerminal(!terminal)} aria-pressed={terminal} title={t('Terminal')} aria-label={t('Terminal')} className={cn('rounded-md p-1.5 transition hover:bg-panel2', terminal ? 'bg-panel2 text-fg' : 'text-muted hover:text-fg')}><PanelBottom className="size-4" /></button>
            <Link to="/" aria-label={t('Trang chủ')} title={t('Trang chủ')} className="rounded-md p-1.5 text-muted transition hover:bg-panel2 hover:text-fg"><House className="size-4" /></Link>
          </div>
        </header>

        <div className="flex min-h-0 flex-1">
          {/* Explorer */}
          <aside className={cn('min-w-0 shrink-0 flex-col border-r border-line bg-panel max-md:flex-1 md:flex md:w-64', pane === 'files' ? 'flex' : 'hidden')} aria-label={t('Dự án')}>
            <div className="flex h-9 shrink-0 items-center gap-1 border-b border-line px-1.5">
              {([['files', t('Tệp'), FolderTree, 0], ['changes', t('Thay đổi'), GitCompare, git.data?.files.length ?? 0]] as const).map(([id, label, Icon, n]) => (
                <button key={id} onClick={() => setSide(id)} aria-pressed={side === id} className={cn('flex h-7 items-center gap-1.5 rounded-md px-2 text-xs font-medium transition', side === id ? 'bg-panel2 text-fg' : 'text-muted hover:text-fg')}>
                  <Icon className="size-3.5" />{label}{n > 0 && <span className="rounded bg-warn/20 px-1 text-[10px] text-warn">{n}</span>}
                </button>
              ))}
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto">
              {side === 'files' ? (files.isLoading ? <Loading /> : <ProjectTree files={files.data ?? []} active={activeTab?.kind === 'file' ? activeTab.path : null} changes={changes} onOpen={(p) => openTab(p)} />)
                : <ChangesList files={git.data} repo={git.data?.repo !== false} onOpen={(f) => openTab(f.path, 'diff', f.status)} />}
            </div>
          </aside>

          {/* Editor + terminal */}
          <main className={cn('min-w-0 flex-1 flex-col md:flex', pane === 'editor' ? 'flex' : 'hidden')}>
            <div className="flex h-9 shrink-0 items-end overflow-x-auto border-b border-line bg-panel" role="tablist">
              {tabs.map((tab) => (
                <div key={tab.key} role="tab" aria-selected={active === tab.key} className={cn('group flex h-9 shrink-0 items-center gap-2 border-r border-line px-3 text-[13px]', active === tab.key ? 'bg-bg text-fg' : 'text-muted hover:text-fg')}>
                  <button onClick={() => setActive(tab.key)} className="flex items-center gap-1.5">
                    {tab.kind === 'diff' ? <GitCompare className="size-3.5 text-warn" /> : <FileCode className="size-3.5" />}
                    <span className="max-w-[12rem] truncate">{tab.path.split('/').pop()}</span>
                    {tab.kind === 'diff' && <span className="text-[10px] text-muted">diff</span>}
                    {tab.kind === 'file' && drafts[tab.path] !== undefined && <span className="size-2 rounded-full bg-accent" aria-label={t('Chưa lưu')} />}
                  </button>
                  <button onClick={() => closeTab(tab.key)} aria-label={t('Đóng')} className="rounded p-0.5 text-muted opacity-0 transition hover:bg-panel2 hover:text-fg group-hover:opacity-100 focus:opacity-100"><X className="size-3" /></button>
                </div>
              ))}
              {dirtyCount > 0 && <span className="ml-auto shrink-0 px-3 pb-2 text-[11px] text-muted">{t('{n} file chưa lưu', { n: dirtyCount })}</span>}
            </div>
            <div className="min-h-0 flex-1">
              {!activeTab ? (
                <div className="grid size-full place-items-center text-center text-sm text-muted"><div><FileCode className="mx-auto mb-3 size-8 opacity-50" /><p>{t('Chọn một file ở cây thư mục để xem và sửa.')}</p><p className="mt-1 text-xs">{t('Agent sửa file nào, file đó hiện ở mục Thay đổi kèm diff.')}</p></div></div>
              ) : activeTab.kind === 'diff' ? (
                <Diff key={activeTab.key} sid={sid} file={{ path: activeTab.path, status: activeTab.status ?? 'modified' }} onBack={() => closeTab(activeTab.key)} onReverted={() => { closeTab(activeTab.key); afterRevert() }} />
              ) : (
                <FileTab key={activeTab.key} sid={sid} path={activeTab.path} draft={drafts[activeTab.path]} onDraft={(v) => setDrafts((d) => { const { [activeTab.path]: _, ...rest } = d; return v === undefined ? rest : { ...rest, [activeTab.path]: v } })} onSaved={() => { void qc.invalidateQueries({ queryKey: ['file', sid, activeTab.path] }); void qc.invalidateQueries({ queryKey: ['git', sid] }) }} />
              )}
            </div>
            {terminal && <div className="h-56 shrink-0 border-t border-line bg-bg"><div className="flex h-7 items-center border-b border-line px-3 text-[11px] font-semibold uppercase tracking-wide text-muted">{t('Terminal')}</div><div className="h-[calc(100%-1.75rem)]"><TerminalTab items={chat.items} /></div></div>}
          </main>

          {/* Chat cua agent */}
          <section className={cn('relative min-w-0 flex-col border-l border-line bg-panel max-md:flex-1 md:flex md:shrink-0', pane === 'chat' ? 'flex' : 'hidden')}
            style={{ width: wide ? `max(280px, min(${chatW}px, calc(100vw - 256px - 280px)))` : undefined }} aria-label={t('Trò chuyện với agent')}>
            <div role="separator" aria-orientation="vertical" aria-label={t('Kéo để đổi độ rộng')} className="absolute left-0 top-0 z-10 h-full w-1.5 cursor-col-resize transition hover:bg-accent/40"
              onPointerDown={(e) => { drag.current = true; (e.target as HTMLElement).setPointerCapture(e.pointerId) }}
              onPointerMove={(e) => { if (drag.current) setChatW(Math.min(760, Math.max(320, window.innerWidth - e.clientX))) }}
              onPointerUp={() => { drag.current = false }} />
            <div className="flex h-9 shrink-0 items-center gap-2 border-b border-line px-3 text-xs font-semibold uppercase tracking-wide text-muted">Agent{chat.busy && <LoaderCircle className="size-3.5 animate-spin text-accent" />}</div>
            <div ref={scroller} onScroll={(e) => { const el = e.currentTarget; stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80 }} className="min-h-0 flex-1 overflow-y-auto">
              <div className="space-y-4 px-3 py-4">
                {chat.items.length === 0 ? (
                  <div className="pt-6 text-center">
                    <p className="text-sm font-medium">{t('Nhờ agent làm việc trong dự án này')}</p>
                    <div className="mt-4 grid gap-2">{IDEAS.map((s) => <button key={s} onClick={() => idea(t(s))} className="rounded-lg border border-line bg-bg px-3 py-2 text-left text-[13px] text-muted transition hover:border-accent/60 hover:text-fg">{t(s)}</button>)}</div>
                  </div>
                ) : chat.items.map((it) => (
                  <MessageView key={it.key} item={it} onDecide={(aid, ok) => void chat.decide(aid, ok)} onOpenFile={(p) => openTab(p)}
                    canAct={!chat.busy} isLastUser={it === lastUser} isLastAssistant={it === lastAssistant} onEdit={(txt) => void resend(txt)} onRegenerate={() => void resend()} />
                ))}
                {chat.busy && chat.status && <p className="flex items-center gap-2 text-xs text-muted" role="status"><LoaderCircle className="size-3.5 animate-spin text-accent" />{chat.status}</p>}
              </div>
            </div>
            <PlanCard items={chat.plan} />
            <Composer mentions={(mcp.data ?? []).filter((s) => s.config.enabled).map((s) => ({ name: s.name, brand: mcpBrand(s.config), status: s.status, tools: s.tools.length }))}
              value={text} onChange={setText} onSend={submit} onStop={chat.stop} busy={chat.busy} attachments={attachments} uploading={false}
              onAttach={() => toast(t('Chế độ Code đọc file trực tiếp từ dự án, không cần đính kèm.'))} onRemoveAttachment={(p) => setAttachments((a) => a.filter((x) => x !== p))} skills={skills.data ?? []}
              docs={false} onDocs={() => {}} docsReady={false} permission={permission} onPermission={setPermission} provider={prov} onProvider={setProvider} effort={effort} onEffort={setEffort}
              providers={providers.map((id) => ({ id, model: cfg.data.config.providers[id].model, type: cfg.data.config.providers[id].type }))} />
          </section>
        </div>
      </div>
    </SessionContext.Provider>
  )
}

function ChangesList({ files, repo, onOpen }: { files: GitStatus | undefined; repo: boolean; onOpen: (f: GitFile) => void }) {
  if (!repo) return <p className="p-4 text-center text-xs text-muted">{t('Dự án này chưa dùng git. Chạy “git init” trong thư mục dự án để xem thay đổi.')}</p>
  if (!files?.files.length) return <p className="p-4 text-center text-xs text-muted">{t('Chưa có thay đổi nào. Khi agent sửa code, file sẽ hiện ở đây.')}</p>
  return (
    <ul className="py-1 text-[13px]">
      {files.files.map((f) => (
        <li key={f.path}>
          <button onClick={() => onOpen(f)} className="flex h-[26px] w-full items-center gap-2 px-3 text-left transition hover:bg-panel2" title={f.path}>
            <span className={cn('w-3 shrink-0 text-[10px] font-semibold', f.status === 'new' ? 'text-ok' : f.status === 'deleted' ? 'text-bad' : 'text-warn')}>{f.status === 'new' ? 'U' : f.status === 'deleted' ? 'D' : 'M'}</span>
            <span className="min-w-0 flex-1 truncate font-mono text-[12px]">{f.path}</span>
          </button>
        </li>
      ))}
    </ul>
  )
}
