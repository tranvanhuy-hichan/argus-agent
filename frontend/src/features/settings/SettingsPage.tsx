import { useEffect, useState } from 'react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { Field, Input } from '@/components/ui/Form'
import { ErrorNote, Loading, Page, PageHeader } from '@/components/ui/misc'
import { Switch } from '@/components/ui/Switch'
import { useToast } from '@/components/ui/Toast'
import { useConfig, useSaveConfig } from '@/lib/queries'
import type { AppConfig, ToolInfo } from '@/lib/types'
import { errMsg } from '@/lib/utils'

const RISK: Record<ToolInfo['risk'], { label: string; tone: 'ok' | 'info' | 'warn' | 'bad' }> = {
  safe: { label: 'An toàn', tone: 'ok' },
  file: { label: 'Truy cập file', tone: 'info' },
  network: { label: 'Mạng', tone: 'warn' },
  exec: { label: 'Chạy lệnh', tone: 'bad' },
  mcp: { label: 'MCP', tone: 'info' },
}

export function SettingsPage() {
  const cfg = useConfig()
  const save = useSaveConfig()
  const toast = useToast()
  const [agent, setAgent] = useState<AppConfig['agent'] | null>(null)
  const [hub, setHub] = useState('')

  useEffect(() => { if (cfg.data) { setAgent(cfg.data.config.agent); setHub(cfg.data.config.clawhub_url) } }, [cfg.data])
  if (cfg.error) return <Page><ErrorNote error={cfg.error} /></Page>
  if (!agent || !cfg.data) return <Loading />
  const dirty = JSON.stringify(agent) !== JSON.stringify(cfg.data.config.agent) || hub !== cfg.data.config.clawhub_url
  const num = (k: 'max_steps' | 'max_history') => (e: React.ChangeEvent<HTMLInputElement>) => setAgent({ ...agent, [k]: Number(e.target.value) })

  return (
    <Page>
      <PageHeader title="Cài đặt" subtitle="Hành vi của agent và quyền sử dụng tool." action={
        <Button variant="primary" disabled={!dirty} loading={save.isPending}
          onClick={() => save.mutate({ ...cfg.data.config, agent, clawhub_url: hub }, { onSuccess: () => toast('Đã lưu cài đặt'), onError: (e) => toast(errMsg(e), 'bad') })}>Lưu thay đổi</Button>
      } />
      <div className="space-y-4">
        <Card>
          <CardHeader title="Agent" />
          <div className="grid gap-4 p-5 sm:grid-cols-2">
            <Field label="Số bước tối đa mỗi lượt" hint="Mỗi lần gọi tool tính là một bước."><Input type="number" min={1} max={50} value={agent.max_steps} onChange={num('max_steps')} /></Field>
            <Field label="Số tin nhắn gửi kèm" hint="Model nhỏ nên để thấp (10–30) vì context ngắn."><Input type="number" min={4} max={500} value={agent.max_history} onChange={num('max_history')} /></Field>
            <div className="sm:col-span-2"><Field label="Thư mục workspace"><Input value={agent.workspace} onChange={(e) => setAgent({ ...agent, workspace: e.target.value })} /></Field></div>
            <div className="flex items-start justify-between gap-4 sm:col-span-2">
              <div>
                <p className="text-sm font-medium">Xác nhận trước khi chạy lệnh shell</p>
                <p className="text-xs text-muted">Khuyến nghị bật, đặc biệt khi cài skill từ internet.</p>
              </div>
              <Switch checked={agent.confirm_exec} onChange={(v) => setAgent({ ...agent, confirm_exec: v })} label="Xác nhận lệnh shell" />
            </div>
          </div>
        </Card>
        <Card>
          <CardHeader title="Tools" hint="Tắt tool nào thì agent không nhìn thấy và không gọi được tool đó. Ít tool giúp model nhỏ chọn đúng hơn." />
          {cfg.data.tools.map((t) => (
            <div key={t.name} className="flex items-center gap-4 border-b border-line px-5 py-3 last:border-b-0">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2"><span className="font-mono text-[13px] font-medium">{t.name}</span><Badge tone={RISK[t.risk].tone}>{RISK[t.risk].label}</Badge></div>
                <p className="text-xs text-muted">{t.description}</p>
              </div>
              <Switch checked={agent.tools_enabled[t.name] !== false} onChange={(v) => setAgent({ ...agent, tools_enabled: { ...agent.tools_enabled, [t.name]: v } })} label={`Bật tool ${t.name}`} />
            </div>
          ))}
        </Card>
        <Card>
          <CardHeader title="ClawHub" hint="Địa chỉ registry để tải skill." />
          <div className="p-5"><Field label="URL"><Input value={hub} onChange={(e) => setHub(e.target.value)} /></Field></div>
        </Card>
      </div>
    </Page>
  )
}
