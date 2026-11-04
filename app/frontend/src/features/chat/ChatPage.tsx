import { useCallback, useEffect, useRef, useState } from 'react'
import { AgentMark } from '../../components/ui/AgentMark'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { Activity, Download, Folder, FolderTree, LoaderCircle, PanelLeft, Terminal, Upload } from 'lucide-react'
import { Loading } from '@/components/ui/misc'
import { useToast } from '@/components/ui/Toast'
import { useConfig, useMcp, useSessions, useSkills } from '@/lib/queries'
import { mcpBrand } from '@/features/integrations/brands'
import { t, tk } from '@/lib/i18n.ts'
import { errMsg } from '@/lib/utils'
import { Composer } from './Composer'
import type { Effort, Permission } from './permissions'
import { MessageView } from './MessageView'
import { PlanCard } from './PlanCard'
import { SessionContext } from './session'
import { SessionList } from './SessionList'
import { useChat, type Item } from './useChat'
import { WorkspacePanel, type PanelTab } from './WorkspacePanel'

const SUGGESTIONS = [tk('Bạn làm được những gì?'), tk('Viết script Python đọc file CSV tôi đính kèm và vẽ biểu đồ, lưu ra file .png'), tk('Tìm trên web tin mới nhất về Python 3.14 và tóm tắt'), tk('Liệt kê các skill bạn đang có')]

const store = {
  get: (k: string, d: string) => { try { return localStorage.getItem(k) ?? d } catch { return d } },
  set: (k: string, v: string) => { try { localStorage.setItem(k, v) } catch { /* che do rieng tu */ } },
}

const PANEL_BUTTONS: { id: PanelTab; label: string; icon: typeof Terminal }[] = [
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

export function ChatPage() {
  const chat = useChat()
  const cfg = useConfig()
  const sessions = useSessions()
  const skills = useSkills()
  const mcp = useMcp()
  const toast = useToast()
  const nav = useNavigate()
  const location = useLocation()
  const [params, setParams] = useSearchParams()
  const [text, setText] = useState('')
  const [provider, setProvider] = useState<string | null>(null)
  const [permission, setPermission] = useState<Permission>('default') // moi hoi thoai bat dau o 'Mac dinh', khong luu lai
  const [effort, setEffort] = useState<Effort>(() => (store.get('effort', 'auto') as Effort))
  const [attachments, setAttachments] = useState<string[]>([])
  const [uploading, setUploading] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [panelOpen, setPanelOpen] = useState(() => store.get('panel-open', '0') === '1')
  const [panelWidth, setPanelWidth] = useState(() => Number(store.get('panel-width', '460')))
  const [sessionsOpen, setSessionsOpen] = useState(() => store.get('sessions-open', '1') === '1')
  const [tab, setTab] = useState<PanelTab>('files')
  const [openPath, setOpenPath] = useState<string | null>(null)
  const scroller = useRef<HTMLDivElement>(null)
  const stick = useRef(true)

  const initial = (location.state as { prompt?: string } | null)?.prompt
  const sentInitial = useRef(false)
  useEffect(() => {
    if (initial && !sentInitial.current && cfg.data) {
      sentInitial.current = true
      nav('.', { replace: true, state: null })
      void chat.send(initial, null)
    }
  }, [initial, cfg.data, chat, nav])

  const wanted = params.get('session')
  useEffect(() => {
    if (wanted) { void chat.open(wanted); setParams({}, { replace: true }) }
  }, [wanted, chat, setParams])

  useEffect(() => {
    const el = scroller.current
    if (el && stick.current) el.scrollTop = el.scrollHeight
  }, [chat.items, chat.status])
  useEffect(() => { store.set('effort', effort) }, [effort])
  useEffect(() => { store.set('panel-open', panelOpen ? '1' : '0') }, [panelOpen])
  useEffect(() => { store.set('sessions-open', sessionsOpen ? '1' : '0') }, [sessionsOpen])
  useEffect(() => { store.set('panel-width', String(panelWidth)) }, [panelWidth])

  const togglePanel = (id: PanelTab) => {
    if (panelOpen && tab === id) setPanelOpen(false)
    else { setTab(id); setPanelOpen(true) }
  }
  const openFile = useCallback((p: string) => { setPanelOpen(true); setTab('files'); setOpenPath(p) }, [])
  const onNew = () => { chat.reset(); setAttachments([]); setOpenPath(null); setPermission('default') }
  const onOpen = (id: string) => { setOpenPath(null); setAttachments([]); setPermission('default'); void chat.open(id) }

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
    void chat.send(text, active, attachments, { permission, effort })
    setText('')
    setAttachments([])
  }
  const resend = async (override?: string) => {
    const last = await chat.rewindLast()
    if (!last) return
    stick.current = true
    void chat.send(override ?? last.text, active, last.attachments)
  }
  const download = () => {
    const blob = new Blob([exportMarkdown(chat.items)], { type: 'text/markdown' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = t('hoi-thoai-{id}.md', { id: chat.sessionId ?? t('moi') })
    a.click()
    URL.revokeObjectURL(a.href)
  }

  return (
    <SessionContext.Provider value={chat.sessionId}>
    <div className="flex h-full">
      {sessionsOpen && <SessionList sessions={sessions.data ?? []} activeId={chat.sessionId} onOpen={onOpen} onNew={onNew} onDeleted={(id) => { if (id === chat.sessionId) onNew() }} />}

      <section className="relative flex min-w-0 flex-1 flex-col"
        onDragOver={(e) => { if (e.dataTransfer.types.includes('Files')) { e.preventDefault(); setDragging(true) } }}
        onDragLeave={(e) => { if (e.currentTarget === e.target) setDragging(false) }}
        onDrop={(e) => { e.preventDefault(); setDragging(false); void upload([...e.dataTransfer.files]) }}>
        <header className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-line px-4">
          <div className="flex min-w-0 items-center gap-2 text-sm">
            <button onClick={() => setSessionsOpen(!sessionsOpen)} aria-pressed={sessionsOpen} aria-label={t('Danh sách hội thoại')} title={t('Danh sách hội thoại')}
              className="hidden rounded-lg p-1.5 text-muted transition hover:bg-panel2 hover:text-fg lg:block"><PanelLeft className="size-4" /></button>
            <Folder className="size-4 shrink-0 text-muted" aria-hidden />
            <span className="hidden text-muted sm:inline">{t('Không gian làm việc')}</span>
            <span className="hidden text-muted/60 sm:inline" aria-hidden>/</span>
            <h1 className="truncate font-medium">{sessions.data?.find((s) => s.id === chat.sessionId)?.title ?? t('Cuộc trò chuyện mới')}</h1>
            <span title={active} className="grid size-5 shrink-0 place-items-center rounded-full bg-ok text-[10px] font-bold text-white" aria-hidden>{active.slice(0, 1).toUpperCase()}</span>
          </div>
          <div className="flex items-center gap-1">
            {chat.items.length > 0 && <button onClick={download} aria-label={t('Xuất hội thoại ra Markdown')} title={t('Xuất Markdown')} className="rounded-lg p-2 text-muted hover:bg-panel2 hover:text-fg"><Download className="size-4" /></button>}
            <div className="hidden items-center gap-0.5 xl:flex" role="group" aria-label={t('Không gian làm việc')}>
              {PANEL_BUTTONS.map(({ id, label, icon: Icon }) => {
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
                <AgentMark className="mb-4" />
                <h2 className="text-xl font-semibold">{t('Mình có thể giúp gì cho bạn?')}</h2>
                <div className="mt-6 grid w-full max-w-xl gap-2 sm:grid-cols-2">
                  {SUGGESTIONS.map((s) => <button key={s} onClick={() => { stick.current = true; void chat.send(t(s), active) }} className="rounded-xl border border-line bg-panel px-3.5 py-3 text-left text-sm text-muted transition hover:border-accent/60 hover:text-fg">{t(s)}</button>)}
                </div>
              </div>
            ) : (
              chat.items.map((it) => (
                <MessageView key={it.key} item={it} onDecide={(aid, ok) => void chat.decide(aid, ok)} onOpenFile={openFile}
                  canAct={!chat.busy} isLastUser={it === lastUser} isLastAssistant={it === lastAssistant}
                  onEdit={(txt) => void resend(txt)} onRegenerate={() => void resend()} />
              ))
            )}
            {chat.busy && chat.status && <p className="ml-10 flex items-center gap-2 text-xs text-muted" role="status"><LoaderCircle className="size-3.5 animate-spin text-accent" />{chat.status}</p>}
          </div>
        </div>

        <PlanCard items={chat.plan} />
        <Composer mentions={(mcp.data ?? []).filter((s) => s.config.enabled).map((s) => ({ name: s.name, brand: mcpBrand(s.config), status: s.status, tools: s.tools.length }))} value={text} onChange={setText} onSend={submit} onStop={chat.stop} busy={chat.busy} attachments={attachments} uploading={uploading}
          onAttach={(f) => void upload(f)} onRemoveAttachment={(p) => setAttachments((a) => a.filter((x) => x !== p))} skills={skills.data ?? []}
          permission={permission} onPermission={setPermission} provider={active} onProvider={setProvider} effort={effort} onEffort={setEffort}
          providers={providers.map((id) => ({ id, model: cfg.data.config.providers[id].model, type: cfg.data.config.providers[id].type }))} />

        {dragging && <div className="pointer-events-none absolute inset-0 z-20 grid place-items-center border-2 border-dashed border-accent bg-bg/80"><p className="flex items-center gap-2 text-sm font-medium"><Upload className="size-5 text-accent" />{t('Thả file để đính kèm')}</p></div>}
      </section>

      {panelOpen && <WorkspacePanel sid={chat.sessionId} items={chat.items} filesTick={chat.filesTick} tab={tab} onTab={setTab} openPath={openPath} onOpenPath={setOpenPath} onClose={() => setPanelOpen(false)} width={panelWidth} onWidth={setPanelWidth} />}
    </div>
    </SessionContext.Provider>
  )
}
