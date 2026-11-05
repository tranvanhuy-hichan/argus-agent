import { useCallback, useEffect, useRef, useState } from 'react'
import { AgentLogoStacked } from '../../components/ui/AgentMark'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { Activity, Copy, Download, FileCode, FileSearch, FileText, Folder, FolderTree, GitCompare, LoaderCircle, PanelLeft, Terminal, Upload } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { BrandIcon, detectBrand } from '@/components/ui/BrandIcon'
import { Loading } from '@/components/ui/misc'
import { useToast } from '@/components/ui/Toast'
import { useConfig, useMcp, useSessions, useSkills } from '@/lib/queries'
import { mcpBrand } from '@/features/integrations/brands'
import { t, tk } from '@/lib/i18n.ts'
import { cn, errMsg } from '@/lib/utils'
import { ProjectPicker } from './ProjectPicker'
import { Composer } from './Composer'
import { permStore, type Effort, type Permission } from './permissions'
import { MessageView } from './MessageView'
import { PlanCard } from './PlanCard'
import { SessionContext } from './session'
import { SessionList } from './SessionList'
import { useChat, type Item } from './useChat'
import { WorkspacePanel, type PanelTab } from './WorkspacePanel'

const DOC_SUGGESTIONS = [tk('Tóm tắt các tài liệu này trong 5 ý chính'), tk('Những mốc thời gian hoặc hạn chót nào được nhắc đến?'), tk('Có những con số hoặc chi phí quan trọng nào?'), tk('Có điều khoản hay yêu cầu nào tôi cần đặc biệt lưu ý?')]
const SUGGESTIONS = [tk('Bạn làm được những gì?'), tk('Soạn giúp tôi một email chuyên nghiệp xin dời lịch họp sang tuần sau'), tk('Tìm trên web tin mới nhất về Python 3.14 và tóm tắt'), tk('Viết script Python đọc file CSV tôi đính kèm và vẽ biểu đồ, lưu ra file .png'), tk('Sắp xếp và đặt tên lại các file trong thư mục làm việc theo loại'), tk('Lập kế hoạch học tiếng Anh 30 ngày, lưu thành file Excel')]

const store = {
  get: (k: string, d: string) => { try { return localStorage.getItem(k) ?? d } catch { return d } },
  set: (k: string, v: string) => { try { localStorage.setItem(k, v) } catch { /* che do rieng tu */ } },
}

const PANEL_BUTTONS: { id: PanelTab; label: string; icon: typeof Terminal }[] = [
  { id: 'changes', label: tk('Thay đổi'), icon: GitCompare },
  { id: 'files', label: tk('Tệp'), icon: FolderTree },
  { id: 'terminal', label: tk('Terminal'), icon: Terminal },
  { id: 'activity', label: tk('Hoạt động'), icon: Activity },
]

function exportMarkdown(items: Item[]): string {
  return items.map((i) => {
    if (i.kind === 'user') return `## ${t('Người dùng')}\n\n${i.text}\n`
    if (i.kind === 'assistant') return `## Agent\n\n${i.text}\n`
    if (i.kind === 'tool') return `> **${t('Lệnh gọi tool')} \`${i.name}\`** ${JSON.stringify(i.args)}\n>\n> ${(i.result ?? '').slice(0, 500).replace(/\n/g, '\n> ')}\n`
    return ''
  }).filter(Boolean).join('\n')
}

function exportJson(items: Item[], sessionTitle?: string): string {
  const data = {
    title: sessionTitle || 'Hội thoại Argus',
    exported_at: new Date().toISOString(),
    messages: items.map((i) => {
      if (i.kind === 'tool') {
        return { kind: i.kind, name: i.name, args: i.args, result: i.result }
      }
      if (i.kind === 'user' || i.kind === 'assistant') {
        return { kind: i.kind, text: i.text }
      }
      return { kind: i.kind }
    }),
  }
  return JSON.stringify(data, null, 2)
}




export function ChatPage() {
  const chat = useChat()
  const cfg = useConfig()
  const allSessions = useSessions()
  const sessions = allSessions
  const skills = useSkills()
  const mcp = useMcp()
  const toast = useToast()
  const qc = useQueryClient()
  const nav = useNavigate()
  const location = useLocation()
  const [params, setParams] = useSearchParams()
  const [text, setText] = useState('')
  const [skill, setSkill] = useState<string | null>(null)
  const [provider, setProvider] = useState<string | null>(null)
  const [permission, setPermission] = useState<Permission>('default') // moi hoi thoai bat dau o 'Mac dinh', khong luu lai
  const changePermission = (p: Permission) => { setPermission(p); permStore.set(chat.sessionId, p) }
  useEffect(() => { // hoi thoai moi vua co id: giu quyen da chon luc chua co id
    const sid = chat.sessionId
    if (sid && !permStore.get(sid)) { const n = permStore.get(null); if (n) permStore.set(sid, n) }
  }, [chat.sessionId])
  const [effort, setEffort] = useState<Effort>(() => (store.get('effort', 'auto') as Effort))
  const [temperature, setTemperature] = useState(() => Number(store.get('chat_temperature', '0.7')))
  const [maxTokens, setMaxTokens] = useState(() => Number(store.get('chat_max_tokens', '4096')))
  const changeTemperature = (v: number) => { setTemperature(v); store.set('chat_temperature', String(v)) }
  const changeMaxTokens = (v: number) => { setMaxTokens(v); store.set('chat_max_tokens', String(v)) }
  const [attachments, setAttachments] = useState<string[]>([])
  const [uploading, setUploading] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [panelOpen, setPanelOpen] = useState(() => store.get('panel-open', '0') === '1')
  const [panelWidth, setPanelWidth] = useState(() => Number(store.get('panel-width', '460')))
  const [sessionsOpen, setSessionsOpen] = useState(() => store.get('sessions-open', '1') === '1')
  const [sidebarHovered, setSidebarHovered] = useState(false)
  const sidebarLeaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [tab, setTab] = useState<PanelTab>('files')
  const [openPath, setOpenPath] = useState<string | null>(null)
  const project = sessions.data?.find((s) => s.id === chat.sessionId)?.project ?? ''
  const [useDocs, setUseDocs] = useState(false) // "Hỏi từ tài liệu"
  const kb = useQuery({ queryKey: ['kb'], queryFn: () => api.get<{ stats: { docs: number } }>('/api/knowledge'), refetchInterval: 15_000 })
  const docsReady = (kb.data?.stats.docs ?? 0) > 0
  const isDocs = useDocs && docsReady
  const [pickOpen, setPickOpen] = useState(false)
  const scroller = useRef<HTMLDivElement>(null)
  const stick = useRef(true)
  const [exportOpen, setExportOpen] = useState(false)
  const exportBoxRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!exportOpen) return
    const down = (e: MouseEvent) => { if (!exportBoxRef.current?.contains(e.target as Node)) setExportOpen(false) }
    document.addEventListener('mousedown', down)
    return () => document.removeEventListener('mousedown', down)
  }, [exportOpen])

  const initial = (location.state as { prompt?: string } | null)?.prompt
  const wantDocs = (location.state as { docs?: boolean } | null)?.docs
  const sentInitial = useRef(false)
  useEffect(() => {
    if (initial && !sentInitial.current && cfg.data) {
      sentInitial.current = true
      nav('.', { replace: true, state: null })
      void chat.send(initial, null)
    }
  }, [initial, cfg.data, chat, nav])

  useEffect(() => {
    if (wantDocs) { setUseDocs(true); nav('.', { replace: true, state: null }) }
  }, [wantDocs, nav])

  const wanted = params.get('session')
  // quay lai trang chat (sau khi mo muc khac) thi hien lai hoi thoai truoc do, ke ca khi agent van dang chay
  const restored = useRef(false)
  useEffect(() => {
    if (restored.current || wanted || initial) return
    restored.current = true
    const last = store.get('last-session', '')
    if (last && !chat.sessionId) { setPermission(permStore.get(last) ?? 'default'); void chat.open(last).catch(() => store.set('last-session', '')) }
  }, [wanted, initial, chat])
  useEffect(() => { if (chat.sessionId) store.set('last-session', chat.sessionId) }, [chat.sessionId])
  useEffect(() => {
    if (!wanted) return
    setPermission(permStore.get(wanted) ?? 'default'); void chat.open(wanted); setParams({}, { replace: true })
  }, [wanted, chat, setParams, sessions.data, nav])

  useEffect(() => {
    const el = scroller.current
    if (el && stick.current) el.scrollTop = el.scrollHeight
  }, [chat.items, chat.status])
  // mở dự án: tự bật panel Thay đổi; phiên thường thì không có tab này
  useEffect(() => {
    if (!project && tab === 'changes') setTab('files')
  }, [project, chat.sessionId, tab])
  useEffect(() => { store.set('effort', effort) }, [effort])
  useEffect(() => { store.set('panel-open', panelOpen ? '1' : '0') }, [panelOpen])
  useEffect(() => { store.set('sessions-open', sessionsOpen ? '1' : '0') }, [sessionsOpen])
  useEffect(() => { store.set('panel-width', String(panelWidth)) }, [panelWidth])

  const togglePanel = (id: PanelTab) => {
    if (panelOpen && tab === id) setPanelOpen(false)
    else { setTab(id); setPanelOpen(true) }
  }
  const openFile = useCallback((p: string) => { setPanelOpen(true); setTab('files'); setOpenPath(p) }, [])
  const setProject = async (path: string | null) => {
    try {
      const sid = await chat.ensureSession()
      await api.post(`/api/sessions/${sid}/project`, { path })
      await qc.invalidateQueries({ queryKey: ['sessions'] })
      setPickOpen(false)
      toast(path ? t('Đã bật chế độ Lập trình: agent làm việc trong dự án này') : t('Đã tắt chế độ Lập trình'))
    } catch (e) { toast(errMsg(e), 'bad') }
  }
  const onNew = () => { chat.reset(); store.set('last-session', ''); setAttachments([]); setOpenPath(null); setPermission('default'); permStore.clear(null); setUseDocs(false) }

  useEffect(() => {
    const handleKeyDown = (e: globalThis.KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setSessionsOpen((s) => !s)
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'n') {
        e.preventDefault()
        onNew()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onNew])

  const onOpen = (id: string) => {
    setOpenPath(null); setAttachments([]); setPermission(permStore.get(id) ?? 'default'); void chat.open(id) }

  const upload = async (files: File[]) => {
    if (!files.length) return
    setUploading(true)
    try {
      const sid = await chat.ensureSession()
      const paths: string[] = []
      for (const f of files) {
        const r = await fetch(`/api/sessions/${sid}/upload?name=${encodeURIComponent(f.name)}`, { method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: f })
        if (!r.ok) throw new Error(`${f.name}: ${(await r.json().catch(() => ({ detail: r.statusText }))).detail}`)
        paths.push((await r.json()).path)
      }
      setAttachments((a) => [...a, ...paths])
      chat.bumpFiles()
    } catch (e) {
      toast(errMsg(e), 'bad')
    } finally {
      setUploading(false)
    }
  }

  if (!cfg.data) return <Loading />
  const providers = Object.keys(cfg.data.config.providers)
  const active = provider ?? cfg.data.config.default_provider
  const lastUser = [...chat.items].reverse().find((i) => i.kind === 'user')
  const lastAssistant = [...chat.items].reverse().find((i) => i.kind === 'assistant')

  const submit = () => {
    if (!text.trim() || chat.busy || uploading) return
    stick.current = true
    void chat.send(skill ? `${t('Dùng skill `{name}`: ', { name: skill })}${text}` : text, active, attachments, { permission, effort, docs: isDocs, temperature, max_tokens: maxTokens })
    setText('')
    setSkill(null)
    setAttachments([])
  }
  const resend = async (override?: string) => {
    const last = await chat.rewindLast()
    if (!last) return
    stick.current = true
    void chat.send(override ?? last.text, active, last.attachments)
  }
  const downloadMd = () => {
    const blob = new Blob([exportMarkdown(chat.items)], { type: 'text/markdown' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = t('hoi-thoai-{id}.md', { id: chat.sessionId ?? t('moi') })
    a.click()
    URL.revokeObjectURL(a.href)
    setExportOpen(false)
  }

  const downloadJson = () => {
    const currentTitle = sessions.data?.find((s) => s.id === chat.sessionId)?.title
    const blob = new Blob([exportJson(chat.items, currentTitle)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = t('hoi-thoai-{id}.json', { id: chat.sessionId ?? t('moi') })
    a.click()
    URL.revokeObjectURL(a.href)
    setExportOpen(false)
  }

  const copyConversation = () => {
    navigator.clipboard.writeText(exportMarkdown(chat.items))
    toast(t('Đã sao chép toàn bộ hội thoại vào bộ nhớ tạm'))
    setExportOpen(false)
  }

  return (
    <SessionContext.Provider value={chat.sessionId}>
    <div className="flex h-full">
      {/* Sidebar: hiển thị cố định nếu sessionsOpen, hoặc overlay slide-in khi hover */}
      {sessionsOpen
        ? <SessionList sessions={sessions.data ?? []} activeId={chat.sessionId} onOpen={onOpen} onNew={onNew} onDeleted={(id) => { if (id === chat.sessionId) onNew() }} showDocs={isDocs} />
        : (
          <div
            className="relative hidden lg:block"
            onMouseEnter={() => { if (sidebarLeaveTimer.current) clearTimeout(sidebarLeaveTimer.current); setSidebarHovered(true) }}
            onMouseLeave={() => { sidebarLeaveTimer.current = setTimeout(() => setSidebarHovered(false), 180) }}
          >
            {/* Vùng trigger mỏng */}
            <div className="h-full w-2" />
            {/* Overlay slide-in — luôn render, dùng transform để animate */}
            <div className={cn(
              'absolute left-0 top-0 z-30 h-full transform transition-transform duration-200 ease-in-out drop-shadow-2xl',
              sidebarHovered ? 'translate-x-0' : '-translate-x-full',
            )}>
              <SessionList
                sessions={sessions.data ?? []}
                activeId={chat.sessionId}
                onOpen={(id) => { onOpen(id); setSidebarHovered(false) }}
                onNew={() => { onNew(); setSidebarHovered(false) }}
                onDeleted={(id) => { if (id === chat.sessionId) onNew() }}
                showDocs={isDocs}
              />
            </div>
          </div>
        )
      }

      <section className="relative flex min-w-0 flex-1 flex-col"
        onDragOver={(e) => { if (e.dataTransfer.types.includes('Files')) { e.preventDefault(); setDragging(true) } }}
        onDragLeave={(e) => { if (e.currentTarget === e.target) setDragging(false) }}
        onDrop={(e) => { e.preventDefault(); setDragging(false); void upload([...e.dataTransfer.files]) }}>
        <header className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-line px-4">
          <div className="flex min-w-0 items-center gap-2 text-sm">
            <button onClick={() => setSessionsOpen(!sessionsOpen)} aria-pressed={sessionsOpen} aria-label={t('Danh sách hội thoại')} title={t('Danh sách hội thoại')}
              className="hidden rounded-lg p-1.5 text-muted transition hover:bg-panel2 hover:text-fg lg:block"><PanelLeft className="size-4" /></button>
            <Folder className="size-4 shrink-0 text-muted" aria-hidden />
            <span className="hidden max-w-[16rem] truncate text-muted sm:inline" title={project || undefined}>{project ? project.replace(/^\/home\/[^/]+/, '~') : t('Không gian làm việc')}</span>
            <span className="hidden text-muted/60 sm:inline" aria-hidden>/</span>
            <h1 className="truncate font-medium">{sessions.data?.find((s) => s.id === chat.sessionId)?.title ?? t('Cuộc trò chuyện mới')}</h1>
            <span title={active} className="grid size-5 shrink-0 place-items-center rounded-full bg-ok text-[10px] font-bold text-white" aria-hidden>{active.slice(0, 1).toUpperCase()}</span>
          </div>
          <div className="flex items-center gap-1">
            {chat.items.length > 0 && (
              <div className="relative" ref={exportBoxRef}>
                <button
                  onClick={() => setExportOpen(!exportOpen)}
                  aria-label={t('Xuất hoặc chia sẻ hội thoại')}
                  title={t('Xuất hội thoại')}
                  className={cn('rounded-lg p-2 transition hover:bg-panel2', exportOpen ? 'bg-panel2 text-fg' : 'text-muted hover:text-fg')}
                >
                  <Download className="size-4" />
                </button>
                {exportOpen && (
                  <div className="absolute right-0 top-full z-40 mt-1.5 w-52 overflow-hidden rounded-xl border border-line bg-panel p-1 shadow-xl">
                    <button onClick={downloadMd} className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-xs hover:bg-panel2">
                      <FileText className="size-3.5 text-accent" />
                      <span>{t('Tải file Markdown (.md)')}</span>
                    </button>
                    <button onClick={downloadJson} className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-xs hover:bg-panel2">
                      <FileCode className="size-3.5 text-accent" />
                      <span>{t('Tải file JSON (.json)')}</span>
                    </button>
                    <div className="my-1 border-t border-line/60" />
                    <button onClick={copyConversation} className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-xs hover:bg-panel2">
                      <Copy className="size-3.5 text-muted" />
                      <span>{t('Sao chép vào Clipboard')}</span>
                    </button>
                  </div>
                )}
              </div>
            )}
            <div className="hidden items-center gap-0.5 xl:flex" role="group" aria-label={t('Không gian làm việc')}>
              {PANEL_BUTTONS.filter((x) => project || x.id !== 'changes').map(({ id, label, icon: Icon }) => {
                const on = panelOpen && tab === id
                const count = id === 'terminal' ? chat.items.filter((i) => i.kind === 'tool' && i.name === 'exec').length : id === 'activity' ? chat.items.filter((i) => i.kind === 'tool').length : 0
                return (
                  <button key={id} onClick={() => togglePanel(id)} aria-pressed={on} aria-label={t(label)} title={t(label)}
                    className={`relative rounded-lg p-2 transition hover:bg-panel2 ${on ? 'bg-panel2 text-fg' : 'text-muted hover:text-fg'}`}>
                    <Icon className="size-4" />
                    {count > 0 && <span className="absolute -right-0.5 -top-0.5 min-w-4 rounded-full bg-accent px-1 text-center text-[9px] font-semibold leading-4 text-accent-fg">{count}</span>}
                  </button>
                )
              })}
            </div>
          </div>
        </header>

        <div ref={scroller} onScroll={(e) => { const el = e.currentTarget; stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80 }} className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-4xl space-y-4 px-5 py-6">
            {chat.items.length === 0 ? (
              <div className="flex flex-col items-center pt-[10vh] text-center">
                {isDocs ? <FileSearch className="mb-4 size-12 text-accent" /> : <AgentLogoStacked large className="mb-5" />}
                <h2 className="text-xl font-semibold">{isDocs ? t('Hỏi đáp trên tài liệu của bạn') : t('Mình có thể giúp gì cho bạn?')}</h2>
                {isDocs && <p className="mt-1 text-sm text-muted">{t('Argus chỉ trả lời dựa trên tài liệu bạn đã thêm và ghi rõ nguồn.')}</p>}
                <div className="mt-6 grid w-full max-w-xl gap-2 sm:grid-cols-2">
                  {(isDocs ? DOC_SUGGESTIONS : SUGGESTIONS).map((s) => <button key={s} onClick={() => { stick.current = true; void chat.send(t(s), active) }} className="rounded-xl border border-line bg-panel px-3.5 py-3 text-left text-sm text-muted transition hover:border-accent/60 hover:text-fg">{t(s)}</button>)}
                </div>
              </div>
            ) : (
              chat.items.map((it) => (
                <MessageView key={it.key} item={it} sid={chat.sessionId} onDecide={(aid, ok) => void chat.decide(aid, ok)} onAnswer={(q, a) => void chat.answer(q, a)} onUndo={() => void chat.undo()} onOpenFile={openFile}
                  canAct={!chat.busy} isLastUser={it === lastUser} isLastAssistant={it === lastAssistant}
                  onEdit={(txt) => void resend(txt)} onRegenerate={() => void resend()} />
              ))
            )}
            {chat.busy && chat.status && (
              <p className="ml-10 flex items-center gap-2 text-xs text-muted" role="status">
                <span className="grid size-5 shrink-0 place-items-center rounded-md bg-panel2">
                  <BrandIcon brand={detectBrand(chat.status) || detectBrand(active) || (cfg.data?.config.providers[active] ? detectBrand(cfg.data.config.providers[active]) : null)} className="size-3.5" />
                </span>
                <LoaderCircle className="size-3.5 animate-spin text-accent" />
                <span>{chat.status}</span>
              </p>
            )}
          </div>
        </div>

        <PlanCard items={chat.plan} />
        <Composer project={project} onCode={() => (project ? void setProject(null) : setPickOpen(true))} mentions={(mcp.data ?? []).filter((s) => s.config.enabled).map((s) => ({ name: s.name, brand: mcpBrand(s.config), status: s.status, tools: s.tools.length }))} value={text} onChange={setText} skill={skill} onSkill={setSkill} onSend={submit} onStop={chat.stop} busy={chat.busy} attachments={attachments} uploading={uploading}
          onAttach={(f) => void upload(f)} onRemoveAttachment={(p) => setAttachments((a) => a.filter((x) => x !== p))} skills={skills.data ?? []}
          docs={isDocs} onDocs={setUseDocs} docsReady={docsReady} permission={permission} onPermission={changePermission} provider={active} onProvider={setProvider} effort={effort} onEffort={setEffort}
          temperature={temperature} onTemperature={changeTemperature} maxTokens={maxTokens} onMaxTokens={changeMaxTokens}
          providers={providers.map((id) => ({ id, model: cfg.data.config.providers[id].model, type: cfg.data.config.providers[id].type }))} />

        {dragging && <div className="pointer-events-none absolute inset-0 z-20 grid place-items-center border-2 border-dashed border-accent bg-bg/80"><p className="flex items-center gap-2 text-sm font-medium"><Upload className="size-5 text-accent" />{t('Thả file để đính kèm')}</p></div>}
      </section>

      <ProjectPicker open={pickOpen} onClose={() => setPickOpen(false)} onPick={(p) => void setProject(p)} />
      {panelOpen && <WorkspacePanel sid={chat.sessionId} project={!!project} items={chat.items} filesTick={chat.filesTick} tab={tab} onTab={setTab} openPath={openPath} onOpenPath={setOpenPath} onClose={() => setPanelOpen(false)} width={panelWidth} onWidth={setPanelWidth} />}
    </div>
    </SessionContext.Provider>
  )
}
