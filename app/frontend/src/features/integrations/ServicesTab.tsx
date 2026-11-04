import { useEffect, useMemo, useState } from 'react'
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronRight, ExternalLink, KeyRound, LogOut, Plus, Search, ShieldAlert, Trash2 } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Field, Input } from '@/components/ui/Form'
import { Modal } from '@/components/ui/Modal'
import { ErrorNote, Loading } from '@/components/ui/misc'
import { ServiceLogo } from '@/components/ui/ServiceLogo'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import { useConfig, useMcp, useSaveConfig } from '@/lib/queries'
import type { Catalog, CatalogService, McpServerCfg, McpServerInfo, RegistryItem } from '@/lib/types'
import { cn, errMsg } from '@/lib/utils'
import { t, tk, useLang } from '@/lib/i18n.ts'
import { blankServer, McpServerModal } from './McpServerModal'
import { sameUrl, serverName } from './services'
import { ToolList } from './ToolList'

const STATUS: Record<McpServerInfo['status'], { label: string; tone: 'ok' | 'info' | 'bad' | 'neutral' | 'warn' }> = {
  needs_auth: { label: tk('Cần đăng nhập'), tone: 'warn' }, connected: { label: tk('Đã kết nối'), tone: 'ok' }, connecting: { label: tk('Đang kết nối…'), tone: 'info' },
  error: { label: tk('Lỗi'), tone: 'bad' }, disabled: { label: tk('Đã tắt'), tone: 'neutral' },
}
type Started = { ok: boolean; auth_url?: string; connected?: boolean; error?: string }
type Probe = { kind: 'oauth' | 'oauth-manual' | 'token' | 'open' | 'down'; note: string }
/** Dich vu dang cho nhap token: tu danh muc (co huong dan san) hoac tu thu vien (doan header). */
type TokenAsk = { key: string; name: string; url: string; transport: 'http' | 'sse'; header: string; prefix: string; help?: string; hint?: string; editing?: string }

/** Mo trang cap quyen o tab da mo san luc bam (de khong bi chan popup). */
async function openLogin(name: string, w: Window | null): Promise<Started> {
  const r = await api.post<Started>(`/api/mcp/${name}/oauth/start`)
  if (r.auth_url && w) { w.location.href = r.auth_url; return r }
  w?.close()
  if (!r.ok) throw new Error(r.error ?? t('Không lấy được địa chỉ đăng nhập'))
  return r
}

interface RowProps {
  logo: React.ReactNode; title: string; desc: string; badges?: React.ReactNode; info?: McpServerInfo; busy: boolean
  onUse?: () => void; onLogin?: () => void; onLogout?: () => void; onRemove?: () => void; onToken?: () => void
  onToggleTool: (name: string, on: boolean) => void; toolsEnabled: Record<string, boolean>
}

function Row({ logo, title, desc, badges, info, busy, onUse, onLogin, onLogout, onRemove, onToken, onToggleTool, toolsEnabled }: RowProps) {
  const [open, setOpen] = useState(false)
  const st = info ? STATUS[info.status] : null
  const canOpen = !!info && info.tools.length > 0
  const oauth = !!info?.config.oauth
  return (
    <div className="bg-panel">
      <div className="flex items-center gap-3 px-4 py-3">
        <button onClick={() => canOpen && setOpen(!open)} className={cn('flex min-w-0 flex-1 items-center gap-3 text-left', !canOpen && 'cursor-default')} aria-expanded={open}>
          <ChevronRight className={cn('size-4 shrink-0 text-muted transition', open && 'rotate-90', !canOpen && 'opacity-0')} />
          <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-panel2">{logo}</span>
          <span className="min-w-0 flex-1">
            <span className="flex flex-wrap items-center gap-2"><span className="font-medium">{title}</span>{badges}{st && <Badge tone={st.tone}>{t(st.label)}</Badge>}{info?.status === 'connected' && <span className="text-xs text-muted">{t('{n} tool', { n: info.tools.length })}</span>}</span>
            <span className="block truncate text-xs text-muted">{desc}</span>
          </span>
        </button>
        {!info ? <Button size="sm" variant="primary" onClick={onUse} loading={busy}>{t('Dùng')}</Button>
          : oauth ? (info.status === 'needs_auth' || !info.logged_in
            ? <Button size="sm" variant="primary" onClick={onLogin} loading={busy}><KeyRound className="size-3.5" />{t('Đăng nhập')}</Button>
            : <Button size="sm" onClick={onLogout}><LogOut className="size-3.5" />{t('Đăng xuất')}</Button>)
            : onToken && <Button size="sm" onClick={onToken}><KeyRound className="size-3.5" />{t('Đổi token')}</Button>}
        {info && <Button size="sm" variant="ghost" onClick={onRemove} aria-label={t('Gỡ {name}', { name: title })}><Trash2 className="size-4" /></Button>}
      </div>
      {info?.status === 'needs_auth' && info.auth_url && <p className="mx-4 mb-3 rounded-lg border border-info/30 bg-info/10 px-3 py-2 text-xs">{t('Đang chờ bạn cho phép ở tab vừa mở…')} <a href={info.auth_url} target="_blank" rel="noreferrer noopener" className="text-info underline">{t('Mở lại trang đăng nhập')}</a></p>}
      {info?.error && <p className="mx-4 mb-3 rounded-lg border border-bad/30 bg-bad/10 px-3 py-2 font-mono text-xs text-bad">{info.error}</p>}
      {open && info && <ToolList tools={info.tools} enabled={toolsEnabled} onToggle={onToggleTool} />}
    </div>
  )
}

function TokenDialog({ ask, onClose, onSave }: { ask: TokenAsk | null; onClose: () => void; onSave: (ask: TokenAsk, token: string) => Promise<void> }) {
  const [token, setToken] = useState('')
  const [busy, setBusy] = useState(false)
  if (!ask) return null
  return (
    <Modal open onClose={onClose} title={t('Nhập token cho {name}', { name: ask.name })}
      footer={<><Button onClick={onClose}>{t('Hủy')}</Button><Button variant="primary" loading={busy} disabled={!token.trim()} onClick={() => { setBusy(true); void onSave(ask, token.trim()).finally(() => setBusy(false)) }}>{t('Lưu và kết nối')}</Button></>}>
      <div className="space-y-4">
        {ask.help && <a href={ask.help} target="_blank" rel="noreferrer noopener" className="inline-flex items-center gap-1.5 text-sm text-accent hover:underline"><ExternalLink className="size-3.5" />{t('Mở trang tạo token')}</a>}
        <Field label="Token">
          <Input type="password" autoComplete="off" value={token} onChange={(e) => setToken(e.target.value)} placeholder={t('Dán token vào đây')} className="font-mono" />
        </Field>
      </div>
    </Modal>
  )
}

export function ServicesTab() {
  const lang = useLang()
  const mcp = useMcp()
  const cfg = useConfig()
  const save = useSaveConfig()
  const qc = useQueryClient()
  const toast = useToast()
  const catalog = useQuery({ queryKey: ['mcp-catalog'], queryFn: () => api.get<Catalog>('/api/mcp/catalog'), staleTime: Infinity })
  const [custom, setCustom] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [q, setQ] = useState('')
  const [dq, setDq] = useState('')
  const [ask, setAsk] = useState<TokenAsk | null>(null)
  const refresh = () => { void qc.invalidateQueries({ queryKey: ['mcp'] }) }
  useEffect(() => { const h = setTimeout(() => setDq(q.trim()), 450); return () => clearTimeout(h) }, [q])

  const registry = useInfiniteQuery({
    queryKey: ['mcp-registry', dq], enabled: dq.length >= 2, initialPageParam: '', staleTime: 300_000,
    queryFn: ({ pageParam }) => api.get<{ items: RegistryItem[]; next: string }>(`/api/mcp/registry?q=${encodeURIComponent(dq)}${pageParam ? `&cursor=${encodeURIComponent(pageParam)}` : ''}`),
    getNextPageParam: (last) => last.next || undefined,
  })

  const run = useMutation({
    mutationFn: async (job: { key: string; fn: (w: Window | null) => Promise<Started | void>; login: boolean }) => {
      setBusy(job.key)
      const w = job.login ? window.open('', '_blank') : null  // mo tab ngay luc bam, dieu huong sau
      try { return await job.fn(w) } catch (e) { w?.close(); throw e } finally { setBusy(null) }
    },
    onSuccess: (r) => { if (r && 'ok' in r) toast(r.connected ? t('Đã kết nối') : t('Hãy cho phép ở tab vừa mở, rồi quay lại đây.')); refresh() },
    onError: (e) => toast(errMsg(e), 'bad'),
  })

  const servers = cfg.data?.config.mcp_servers ?? {}
  const toolsEnabled = cfg.data?.config.agent.tools_enabled ?? {}
  const pick = (d: { vi: string; en: string }) => (lang === 'en' ? d.en : d.vi)
  const services = useMemo(() => catalog.data?.services ?? [], [catalog.data])
  const nameFor = (url: string) => Object.entries(servers).find(([, c]) => (c.service || c.oauth) && sameUrl(c.url, url))?.[0]
  const infoOf = (name?: string) => (name ? mcp.data?.find((s) => s.name === name) : undefined)
  const catalogUrls = services.map((s) => s.url)
  const mine = Object.entries(servers).filter(([, c]) => (c.service || c.oauth) && !catalogUrls.some((u) => sameUrl(u, c.url)))

  const needle = q.trim().toLowerCase()
  const shown = useMemo(() => (needle ? services.filter((s) => `${s.name} ${s.id} ${s.desc.vi} ${s.desc.en}`.toLowerCase().includes(needle)) : services), [services, needle])
  const registryItems = (registry.data?.pages.flatMap((p) => p.items) ?? []).filter((i) => !catalogUrls.some((u) => sameUrl(u, i.url)))

  if (mcp.isLoading || cfg.isLoading || catalog.isLoading) return <Loading />
  const err = mcp.error ?? cfg.error ?? catalog.error
  if (err || !cfg.data || !catalog.data) return <ErrorNote error={err} />

  const addServer = async (name: string, c: McpServerCfg) => { const full = structuredClone(cfg.data.config); full.mcp_servers[name] = c; await save.mutateAsync(full) }
  const base = (url: string, transport: 'http' | 'sse'): McpServerCfg => ({ ...blankServer, transport, url, service: true, enabled: true, confirm: true })

  const chooseCatalog = (s: CatalogService) => {
    const existing = nameFor(s.url)
    if (s.auth === 'token') { setAsk({ key: s.id, name: s.name, url: s.url, transport: s.transport, header: s.token!.header, prefix: s.token!.prefix, help: s.token!.help_url, hint: pick(s.token!.hint), editing: existing }); return }
    run.mutate({ key: s.id, login: s.auth === 'oauth', fn: async (w) => {
      const name = existing ?? serverName(s.id, Object.keys(servers))
      await addServer(name, { ...base(s.url, s.transport), oauth: s.auth === 'oauth' })
      return s.auth === 'oauth' ? openLogin(name, w) : undefined
    } })
  }
  const chooseRegistry = (i: RegistryItem) => {
    const warn = i.community ? t('Server do cộng đồng đăng, Argus không kiểm duyệt. Công cụ của nó vẫn phải qua bước xin phép, nhưng nội dung nó trả về là dữ liệu bên ngoài. Chỉ dùng nếu bạn tin nguồn này.') : t('Thêm "{name}"?', { name: i.name })
    if (!confirm(`${i.name}\n${i.url}\n\n${warn}`)) return
    run.mutate({ key: i.id, login: false, fn: async () => {
      const p = await api.post<Probe>('/api/mcp/probe', { url: i.url })
      if (p.kind === 'down') throw new Error(t('Không kết nối được tới máy chủ này ({note}).', { note: p.note }))
      const name = serverName(i.id, Object.keys(servers))
      if (p.kind === 'token' || p.kind === 'oauth-manual' || i.needs_header.length) {
        const header = i.needs_header[0] ?? 'Authorization'
        setAsk({ key: i.id, name: i.name, url: i.url, transport: i.transport, header, prefix: header.toLowerCase() === 'authorization' ? 'Bearer ' : '', help: i.website || undefined })
        return
      }
      await addServer(name, { ...base(i.url, i.transport), oauth: p.kind === 'oauth' })
      if (p.kind === 'oauth') { const w = window.open('', '_blank'); try { return await openLogin(name, w) } catch (e) { w?.close(); throw e } }
    } })
  }
  const saveToken = async (a: TokenAsk, token: string) => {
    try {
      const name = a.editing ?? serverName(a.key, Object.keys(servers))
      await addServer(name, { ...base(a.url, a.transport), headers: { [a.header]: a.prefix + token } })
      toast(t('Đã lưu MCP server')); setAsk(null); refresh()
    } catch (e) { toast(errMsg(e), 'bad') }
  }
  const login = (name: string) => run.mutate({ key: name, login: true, fn: (w) => openLogin(name, w) })
  const logout = (name: string) => { if (confirm(t('Đăng xuất khỏi "{name}"? Token đã lưu sẽ bị xóa.', { name }))) run.mutate({ key: name, login: false, fn: async () => { await api.post(`/api/mcp/${name}/oauth/logout`); toast(t('Đã đăng xuất')) } }) }
  const remove = (name: string) => { if (confirm(t('Gỡ "{name}"? Token đăng nhập đã lưu cũng bị xóa.', { name }))) run.mutate({ key: name, login: false, fn: async () => {
    if (servers[name]?.oauth) await api.post(`/api/mcp/${name}/oauth/logout`)
    const c = structuredClone(cfg.data.config)
    delete c.mcp_servers[name]
    await save.mutateAsync(c)
    toast(t('Đã gỡ'))
  } }) }
  const toggleTool = (n: string, on: boolean) => { const c = structuredClone(cfg.data.config); c.agent.tools_enabled = { ...toolsEnabled, [n]: on }; save.mutate(c, { onError: (e) => toast(errMsg(e), 'bad') }) }
  const common = { onToggleTool: toggleTool, toolsEnabled }

  return (
    <div className="space-y-6">
      <div className="relative max-w-xl">
        <Search className="pointer-events-none absolute left-3 top-2.5 size-4 text-muted" />
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('Tìm dịch vụ (ví dụ vercel, github, stripe…)')} aria-label={t('Tìm dịch vụ')} className="pl-9" />
      </div>

      {catalog.data.groups.map((g) => {
        const items = shown.filter((s) => s.group === g.id)
        if (!items.length) return null
        return (
          <section key={g.id}>
            <h3 className="mb-2 flex items-baseline gap-2 text-sm font-semibold">{pick(g.label)}<span className="rounded-md bg-panel2 px-1.5 py-0.5 text-[11px] font-normal text-muted">{items.length}</span></h3>
            <div className="divide-y divide-line overflow-hidden rounded-xl border border-line">
              {items.map((s) => {
                const name = nameFor(s.url)
                return <Row key={s.id} logo={<ServiceLogo id={s.id} name={s.name} color={s.color} />} title={s.name} desc={pick(s.desc)} info={infoOf(name)} busy={busy === s.id || busy === name}
                  badges={s.auth === 'token' ? <Badge tone="info">{t('Cần token')}</Badge> : s.auth === 'open' ? <Badge tone="ok">{t('Không cần đăng nhập')}</Badge> : null} {...common}
                  onUse={() => chooseCatalog(s)} onLogin={() => name && login(name)} onLogout={() => name && logout(name)} onRemove={() => name && remove(name)} onToken={s.auth === 'token' ? () => chooseCatalog(s) : undefined} />
              })}
            </div>
          </section>
        )
      })}
      {needle && shown.length === 0 && <p className="text-sm text-muted">{t('Không có dịch vụ nào trong danh mục khớp “{q}”.', { q })}</p>}

      {dq.length >= 2 && (
        <section>
          <h3 className="text-sm font-semibold">{t('Từ thư viện MCP chính thức')}</h3>
          <p className="mb-2 mt-0.5 flex items-start gap-1.5 text-xs text-warn"><ShieldAlert className="mt-0.5 size-3.5 shrink-0" />{t('Thư viện này do cộng đồng đăng, Argus không kiểm duyệt từng mục. Nguồn có nhãn “Cộng đồng” chưa được xác minh thương hiệu.')}</p>
          {registry.isLoading ? <Loading /> : registry.error ? <ErrorNote error={registry.error} /> : registryItems.length === 0 ? <p className="rounded-xl border border-dashed border-line px-4 py-5 text-center text-sm text-muted">{t('Không tìm thấy dịch vụ từ xa nào khớp “{q}”.', { q: dq })}</p> : (
            <div className="divide-y divide-line overflow-hidden rounded-xl border border-line">
              {registryItems.map((i) => {
                const name = nameFor(i.url)
                return <Row key={i.id + i.url} logo={<ServiceLogo id={i.id} name={i.name} color="6B7280" />} title={i.name} desc={`${i.description || i.url}`} info={infoOf(name)} busy={busy === i.id}
                  badges={<Badge tone={i.community ? 'warn' : 'neutral'}>{i.community ? t('Cộng đồng') : i.publisher}</Badge>} {...common}
                  onUse={() => chooseRegistry(i)} onLogin={() => name && login(name)} onLogout={() => name && logout(name)} onRemove={() => name && remove(name)} />
              })}
            </div>
          )}
          {registry.hasNextPage && <div className="mt-2"><Button size="sm" onClick={() => void registry.fetchNextPage()} loading={registry.isFetchingNextPage}>{t('Xem thêm kết quả')}</Button></div>}
        </section>
      )}

      <section>
        <div className="mb-2 flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold">{t('Dịch vụ do bạn thêm')}</h3>
          <Button size="sm" onClick={() => setCustom(true)}><Plus className="size-3.5" />{t('Thêm dịch vụ khác')}</Button>
        </div>
        {mine.length === 0 ? <p className="rounded-xl border border-dashed border-line px-4 py-6 text-center text-sm text-muted">{t('Chưa có. Dịch vụ nào có MCP từ xa đều thêm được ở đây, hoặc tìm trong thư viện ở ô tìm kiếm phía trên.')}</p> : (
          <div className="divide-y divide-line overflow-hidden rounded-xl border border-line">
            {mine.map(([name, c]) => <Row key={name} logo={<ServiceLogo id={name} name={name} color="6B7280" />} title={name} desc={c.url} info={infoOf(name)} busy={busy === name} {...common}
              onLogin={() => login(name)} onLogout={() => logout(name)} onRemove={() => remove(name)} />)}
          </div>
        )}
      </section>

      <TokenDialog key={ask?.key ?? 'none'} ask={ask} onClose={() => setAsk(null)} onSave={saveToken} />
      <McpServerModal open={custom} kind="service" name={null} initial={{ ...blankServer, transport: 'http', oauth: true }} onClose={() => setCustom(false)}
        onSave={(name, c) => { save.mutate({ ...cfg.data.config, mcp_servers: { ...servers, [name]: { ...c, service: true } } }, { onSuccess: () => { toast(t('Đã lưu MCP server')); refresh() }, onError: (e) => toast(errMsg(e), 'bad') }); setCustom(false) }} />
    </div>
  )
}
