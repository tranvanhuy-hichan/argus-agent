import { useState } from 'react'
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

const STATUS: Record<McpServerInfo['status'], { label: string; tone: 'ok' | 'info' | 'bad' | 'neutral' }> = {
  connected: { label: 'Đã kết nối', tone: 'ok' }, connecting: { label: 'Đang kết nối…', tone: 'info' }, error: { label: 'Lỗi', tone: 'bad' }, disabled: { label: 'Đã tắt', tone: 'neutral' },
}

export function McpTab() {
  const mcp = useMcp()
  const cfg = useConfig()
  const save = useSaveConfig()
  const qc = useQueryClient()
  const toast = useToast()
  const [editing, setEditing] = useState<{ name: string | null; cfg: McpServerCfg } | null>(null)
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

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-2xl text-sm text-muted">Kết nối các MCP server (của bạn hoặc bên thứ ba). Tool của chúng sẽ xuất hiện cho agent với tên dạng <code className="rounded bg-panel2 px-1 font-mono text-xs">tênserver__têntool</code>.</p>
        <Button variant="primary" onClick={() => setEditing({ name: null, cfg: blankServer })}><Plus className="size-4" />Thêm MCP server</Button>
      </div>

      {mcp.data?.length === 0 ? (
        <Card><EmptyState icon={Cable} title="Chưa có MCP server nào" hint="Ví dụ thử nhanh: stdio với lệnh là Python trong .venv và tham số là examples/demo_mcp_server.py." action={<Button variant="primary" onClick={() => setEditing({ name: null, cfg: blankServer })}><Plus className="size-4" />Thêm MCP server</Button>} /></Card>
      ) : mcp.data?.map((s) => {
        const st = STATUS[s.status]
        const expanded = open === s.name
        return (
          <Card key={s.name}>
            <div className="flex items-center gap-4 p-4">
              <button onClick={() => setOpen(expanded ? null : s.name)} aria-expanded={expanded} className="flex min-w-0 flex-1 items-center gap-3 text-left">
                <ChevronRight className={cn('size-4 shrink-0 text-muted transition', expanded && 'rotate-90')} />
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{s.name}</span><Badge>{s.config.transport}</Badge><Badge tone={st.tone}>{st.label}</Badge>
                    {s.status === 'connected' && <span className="text-xs text-muted">{s.tools.length} tool</span>}
                    {!s.config.confirm && <Badge tone="warn">Không hỏi xác nhận</Badge>}
                  </div>
                  <p className="truncate font-mono text-xs text-muted">{s.config.transport === 'stdio' ? `${s.config.command} ${s.config.args.join(' ')}` : s.config.url}</p>
                </div>
              </button>
              <Button size="sm" variant="ghost" onClick={() => reconnect.mutate(s.name)} aria-label={`Kết nối lại ${s.name}`} disabled={s.status === 'disabled'}><RefreshCw className="size-4" /></Button>
              <Button size="sm" variant="ghost" onClick={() => setEditing({ name: s.name, cfg: s.config })} aria-label={`Sửa ${s.name}`}><Pencil className="size-4" /></Button>
              <Button size="sm" variant="ghost" onClick={() => { if (confirm(`Xóa MCP server "${s.name}"?`)) { const { [s.name]: _, ...rest } = servers; persist(rest, undefined, 'Đã xóa') } }} aria-label={`Xóa ${s.name}`}><Trash2 className="size-4" /></Button>
              <Switch checked={s.config.enabled} onChange={(v) => persist({ ...servers, [s.name]: { ...servers[s.name], enabled: v } })} label={`Bật ${s.name}`} />
            </div>
            {s.error && <p className="mx-4 mb-4 rounded-lg border border-bad/30 bg-bad/10 px-3 py-2 font-mono text-xs text-bad">{s.error}</p>}
            {expanded && s.tools.length > 0 && (
              <div className="border-t border-line">
                {s.tools.map((t) => (
                  <div key={t.full_name} className="flex items-center gap-4 border-b border-line px-5 py-2.5 last:border-b-0">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2"><span className="font-mono text-[13px]">{t.full_name}</span>{t.read_only && <Badge tone="ok">read-only</Badge>}</div>
                      <p className="line-clamp-2 text-xs text-muted">{t.description}</p>
                    </div>
                    <Switch checked={toolsEnabled[t.full_name] !== false} onChange={(v) => persist(servers, { ...toolsEnabled, [t.full_name]: v })} label={`Bật tool ${t.full_name}`} />
                  </div>
                ))}
              </div>
            )}
          </Card>
        )
      })}

      <McpServerModal open={!!editing} name={editing?.name ?? null} initial={editing?.cfg ?? blankServer} onClose={() => setEditing(null)}
        onSave={(name, c) => { persist({ ...servers, [name]: c }, undefined, 'Đã lưu MCP server'); setEditing(null) }} />
    </div>
  )
}
