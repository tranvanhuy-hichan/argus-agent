import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Cable, ChevronRight, Pencil, Plus, RefreshCw, Trash2 } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { EmptyState, ErrorNote, Loading } from '@/components/ui/misc'
import { Switch } from '@/components/ui/Switch'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import { useConfig, useMcp, useSaveConfig } from '@/lib/queries'
import type { McpServerCfg, McpServerInfo } from '@/lib/types'
import { cn, errMsg } from '@/lib/utils'
import { blankServer, McpServerModal } from './McpServerModal'
import { ToolList } from './ToolList'
import { t, tk } from '@/lib/i18n.ts'

const STATUS: Record<McpServerInfo['status'], { label: string; tone: 'ok' | 'info' | 'bad' | 'neutral' | 'warn' }> = {
  needs_auth: { label: tk('Cần đăng nhập'), tone: 'warn' },
  connected: { label: tk('Đã kết nối'), tone: 'ok' }, connecting: { label: tk('Đang kết nối…'), tone: 'info' }, error: { label: tk('Lỗi'), tone: 'bad' }, disabled: { label: tk('Đã tắt'), tone: 'neutral' },
}

/** MCP truyen thong: server chay tren may ban (stdio) hoac server HTTP/SSE tu khai bao. Dich vu dang nhap bang tai khoan nam o tab "MCP dich vu". */
export function McpTab({ addSignal = 0 }: { addSignal?: number }) {
  const mcp = useMcp()
  const cfg = useConfig()
  const save = useSaveConfig()
  const qc = useQueryClient()
  const toast = useToast()
  const [editing, setEditing] = useState<{ name: string | null; cfg: McpServerCfg } | null>(null)
  useEffect(() => { if (addSignal > 0) setEditing({ name: null, cfg: blankServer }) }, [addSignal])
  const [open, setOpen] = useState<string | null>(null)

  const refresh = () => { void qc.invalidateQueries({ queryKey: ['mcp'] }) }
  const persist = (servers: Record<string, McpServerCfg>, tools?: Record<string, boolean>, msg?: string) => {
    if (!cfg.data) return
    const c = structuredClone(cfg.data.config)
    c.mcp_servers = servers
    if (tools) c.agent.tools_enabled = tools
    save.mutate(c, { onSuccess: () => { if (msg) toast(msg); setTimeout(refresh, 800) }, onError: (e) => toast(errMsg(e), 'bad') })
  }
  const reconnect = useMutation({ mutationFn: (n: string) => api.post(`/api/mcp/${n}/reconnect`), onSuccess: () => setTimeout(refresh, 500) })

  if (mcp.isLoading || !cfg.data) return <Loading />
  if (mcp.error) return <ErrorNote error={mcp.error} />
  const servers = cfg.data.config.mcp_servers
  const toolsEnabled = cfg.data.config.agent.tools_enabled
  const list = (mcp.data ?? []).filter((s) => !s.config.oauth && !s.config.service)

  return (
    <div className="space-y-4">
      {list.length === 0 ? (
        <Card><EmptyState icon={Cable} title={t('Chưa có MCP server nào')} action={<Button variant="primary" onClick={() => setEditing({ name: null, cfg: blankServer })}><Plus className="size-4" />{t('Thêm MCP server')}</Button>} /></Card>
      ) : list.map((s) => {
        const st = STATUS[s.status]
        const expanded = open === s.name
        return (
          <Card key={s.name}>
            <div className="flex items-center gap-4 p-4">
              <button onClick={() => setOpen(expanded ? null : s.name)} aria-expanded={expanded} className="flex min-w-0 flex-1 items-center gap-3 text-left">
                <ChevronRight className={cn('size-4 shrink-0 text-muted transition', expanded && 'rotate-90')} />
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{s.name}</span><Badge>{s.config.transport}</Badge><Badge tone={st.tone}>{t(st.label)}</Badge>
                    {s.status === 'connected' && <span className="text-xs text-muted">{t('{n} tool', { n: s.tools.length })}</span>}
                    {!s.config.confirm && <Badge tone="warn">{t('Không hỏi xác nhận')}</Badge>}
                  </div>
                  <p className="truncate font-mono text-xs text-muted">{s.config.transport === 'stdio' ? `${s.config.command} ${s.config.args.join(' ')}` : s.config.url}</p>
                </div>
              </button>
              <Button size="sm" variant="ghost" onClick={() => reconnect.mutate(s.name)} aria-label={t('Kết nối lại {name}', { name: s.name })} disabled={s.status === 'disabled'}><RefreshCw className="size-4" /></Button>
              <Button size="sm" variant="ghost" onClick={() => setEditing({ name: s.name, cfg: s.config })} aria-label={t('Sửa {name}', { name: s.name })}><Pencil className="size-4" /></Button>
              <Button size="sm" variant="ghost" onClick={() => { if (confirm(t('Xóa MCP server "{name}"?', { name: s.name }))) { const { [s.name]: _, ...rest } = servers; persist(rest, undefined, t('Đã xóa')) } }} aria-label={t('Xóa {name}', { name: s.name })}><Trash2 className="size-4" /></Button>
              <Switch checked={s.config.enabled} onChange={(v) => persist({ ...servers, [s.name]: { ...servers[s.name], enabled: v } })} label={t('Bật {name}', { name: s.name })} />
            </div>
            {s.error && <p className="mx-4 mb-4 rounded-lg border border-bad/30 bg-bad/10 px-3 py-2 font-mono text-xs text-bad">{s.error}</p>}
            {expanded && <ToolList tools={s.tools} enabled={toolsEnabled} onToggle={(n, on) => persist(servers, { ...toolsEnabled, [n]: on })} />}
          </Card>
        )
      })}

      <McpServerModal open={!!editing} name={editing?.name ?? null} initial={editing?.cfg ?? blankServer} onClose={() => setEditing(null)}
        onSave={(name, c) => { persist({ ...servers, [name]: c }, undefined, t('Đã lưu MCP server')); setEditing(null) }} />
    </div>
  )
}
