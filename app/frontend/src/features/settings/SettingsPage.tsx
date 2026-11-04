import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Download, Upload } from 'lucide-react'
import { api } from '@/lib/api'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { Field, Input, Select } from '@/components/ui/Form'
import { ErrorNote, Loading, Page, PageHeader } from '@/components/ui/misc'
import { Switch } from '@/components/ui/Switch'
import { useToast } from '@/components/ui/Toast'
import { useConfig, useSaveConfig } from '@/lib/queries'
import type { AppConfig, ExtraCfg, SecretsStatus, ToolInfo } from '@/lib/types'
import { errMsg } from '@/lib/utils'
import { t, tk } from '@/lib/i18n.ts'
import { Tabs } from '@/components/ui/Tabs'
import { FeaturesTab } from './FeaturesTab'

const RISK: Record<ToolInfo['risk'], { label: string; tone: 'ok' | 'info' | 'warn' | 'bad' }> = {
  safe: { label: tk('An toàn'), tone: 'ok' },
  file: { label: tk('Truy cập file'), tone: 'info' },
  network: { label: tk('Mạng'), tone: 'warn' },
  exec: { label: tk('Chạy lệnh'), tone: 'bad' },
  mcp: { label: 'MCP', tone: 'info' },
}

function SecretsCard({ s }: { s?: SecretsStatus }) {
  if (!s) return null
  const where = { env: t('biến môi trường ARGUS_MASTER_KEY'), keychain: t('keychain của hệ điều hành'), file: 'data/master.key', none: t('chưa có') }[s.source]
  return (
    <Card>
      <CardHeader title={t('Mã hóa khóa bí mật')} />
      <div className="space-y-3 p-5 text-sm">
        <div className="flex items-center justify-between"><span className="text-muted">{t('Khóa đã mã hóa')}</span><Badge tone="ok">{s.encrypted}</Badge></div>
        <div className="flex items-center justify-between"><span className="text-muted">{t('Khóa còn chữ thường')}</span><Badge tone={s.plaintext ? 'warn' : 'neutral'}>{s.plaintext}</Badge></div>
        <div className="flex items-center justify-between"><span className="text-muted">{t('Nơi giữ khóa chủ')}</span><span className="font-mono text-xs">{where}</span></div>
        {!s.enabled && <p className="text-warn">{t('Mã hóa đã tắt (ARGUS_ENCRYPT=0).')}</p>}
        {s.failed.length > 0 && <p className="rounded-lg border border-bad/30 bg-bad/10 px-3 py-2 text-bad">{t('{n} khóa không giải mã được (mất hoặc sai khóa chủ). Hãy nhập lại trong giao diện hoặc khôi phục khóa chủ.', { n: s.failed.length })}</p>}
        {s.enabled && s.plaintext > 0 && <p className="text-warn">{t('Còn khóa chưa mã hóa. Chạy: argus secrets encrypt')}</p>}
        {s.source === 'file' && <p className="text-xs text-muted">{t('Hãy sao lưu khóa chủ (argus backup --include-key --encrypt): mất nó thì không giải mã lại được các khóa.')}</p>}
      </div>
    </Card>
  )
}

function PasswordCard({ has }: { has: boolean }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const m = useMutation({
    mutationFn: (v: { current: string; new: string }) => api.post<{ required: boolean }>('/api/auth/password', v),
    onSuccess: (r) => { toast(r.required ? t('Đã đặt mật khẩu') : t('Đã gỡ mật khẩu')); setCurrent(''); setNext(''); void qc.invalidateQueries({ queryKey: ['config'] }); void qc.invalidateQueries({ queryKey: ['auth-status'] }) },
    onError: (e) => toast(errMsg(e), 'bad'),
  })
  return (
    <Card>
      <CardHeader title={t('Bảo mật giao diện')} hint={has ? t('Giao diện đang yêu cầu mật khẩu.') : t('Chưa đặt mật khẩu: chỉ an toàn khi chỉ mình bạn dùng máy này. Hãy đặt mật khẩu nếu mở giao diện cho mạng LAN.')} />
      <div className="grid gap-4 p-5 sm:grid-cols-2">
        {has && <Field label={t('Mật khẩu hiện tại')}><Input type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} /></Field>}
        <Field label={has ? t('Mật khẩu mới (để trống để gỡ mật khẩu)') : t('Mật khẩu mới (ít nhất 8 ký tự)')}><Input type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} /></Field>
        <div className="col-span-full"><Button variant={has && !next ? 'danger' : 'primary'} loading={m.isPending} disabled={has ? !current : next.length < 8} onClick={() => m.mutate({ current, new: next })}>{has ? (next ? t('Đổi mật khẩu') : t('Gỡ mật khẩu')) : t('Đặt mật khẩu')}</Button></div>
      </div>
    </Card>
  )
}

function BackupRestoreCard() {
  const toast = useToast()
  const [restoring, setRestoring] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleRestore = async (file: File) => {
    if (!confirm(t('Khôi phục sẽ ghi đè toàn bộ dữ liệu hiện tại bằng dữ liệu trong file sao lưu. Hệ thống sẽ tự động tạo một bản sao lưu dự phòng trước khi áp dụng. Bạn có chắc chắn muốn khôi phục?'))) {
      return
    }
    setRestoring(true)
    try {
      const res = await fetch('/api/backup/restore', {
        method: 'POST',
        headers: { 'Content-Type': 'application/octet-stream' },
        body: file,
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(err.detail || 'Lỗi khôi phục')
      }
      toast(t('Khôi phục thành công! Đang tải lại dữ liệu...'))
      setTimeout(() => {
        window.location.reload()
      }, 1500)
    } catch (e) {
      toast(errMsg(e), 'bad')
      setRestoring(false)
    }
  }

  return (
    <Card>
      <CardHeader
        title={t('Sao lưu & Khôi phục dữ liệu')}
        hint={t('Sao lưu toàn bộ cấu hình, tài liệu, trí nhớ, cơ sở dữ liệu hội thoại và không gian làm việc.')}
      />
      <div className="p-5">
        <div className="flex flex-wrap items-center gap-3">
          <a
            href="/api/backup/download"
            download
            className="inline-flex items-center gap-2 rounded-xl border border-line bg-panel2 px-4 py-2.5 text-sm font-medium transition hover:border-accent hover:text-accent"
          >
            <Download className="size-4 text-accent" />
            {t('Tải bản sao lưu (.tar.gz)')}
          </a>

          <input
            ref={fileInputRef}
            type="file"
            hidden
            accept=".tar.gz,.enc,application/gzip"
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) void handleRestore(file)
              e.target.value = ''
            }}
          />

          <Button
            loading={restoring}
            onClick={() => fileInputRef.current?.click()}
          >
            <Upload className="size-4" />
            {t('Khôi phục từ file')}
          </Button>
        </div>
        <p className="mt-3 text-xs text-muted">
          {t('Khi khôi phục, hệ thống tự động lưu bản sao lưu an toàn (pre-restore) để bạn có thể quay lại nếu cần.')}
        </p>
      </div>
    </Card>
  )
}


export function SettingsPage() {
  const cfg = useConfig()
  const save = useSaveConfig()
  const toast = useToast()
  const [agent, setAgent] = useState<AppConfig['agent'] | null>(null)
  const [hub, setHub] = useState('')
  const [extra, setExtra] = useState<ExtraCfg | null>(null)
  const [params, setParams] = useSearchParams()
  const tab = (['agent', 'features', 'tools', 'security'] as const).find((t) => t === params.get('tab')) ?? 'agent'

  useEffect(() => { if (cfg.data) { setAgent(cfg.data.config.agent); setHub(cfg.data.config.clawhub_url); const c = cfg.data.config; setExtra({ browser: c.browser, memory: c.memory, media: c.media, computer: c.computer, agents: c.agents }) } }, [cfg.data])
  if (cfg.error) return <Page><ErrorNote error={cfg.error} /></Page>
  if (!agent || !extra || !cfg.data) return <Loading />
  const dirty = JSON.stringify(agent) !== JSON.stringify(cfg.data.config.agent) || hub !== cfg.data.config.clawhub_url || JSON.stringify(extra) !== JSON.stringify((({ browser, memory, media, computer, agents }) => ({ browser, memory, media, computer, agents }))(cfg.data.config))
  const num = (k: 'max_steps' | 'max_history') => (e: React.ChangeEvent<HTMLInputElement>) => setAgent({ ...agent, [k]: Number(e.target.value) })

  const TAB_ITEMS = [
    { id: 'agent' as const, label: t('Cơ bản') },
    { id: 'features' as const, label: t('Tính năng & Trí nhớ') },
    { id: 'tools' as const, label: t('Công cụ') },
    { id: 'security' as const, label: t('An toàn & Bảo mật') },
  ]

  return (
    <Page>
      <PageHeader title={t('Cài đặt')} action={
        <Button variant="primary" disabled={!dirty} loading={save.isPending}
          onClick={() => save.mutate({ ...cfg.data.config, ...extra, agent, clawhub_url: hub }, { onSuccess: () => toast(t('Đã lưu cài đặt')), onError: (e) => toast(errMsg(e), 'bad') })}>{t('Lưu thay đổi')}</Button>
      } />

      <Tabs
        value={tab}
        onChange={(id) => setParams(id === 'agent' ? {} : { tab: id }, { replace: true })}
        tabs={TAB_ITEMS}
      />

      <div className="mt-5 w-full space-y-4">
        {tab === 'agent' && (
          <>
        <Card>
          <CardHeader title={t('Agent')} />
          <div className="grid gap-4 p-5 sm:grid-cols-2 xl:grid-cols-3">
            <div className="-mx-5 flex items-center justify-between gap-4 border-b border-line/60 px-5 pb-4 last:border-b-0 last:pb-0 col-span-full">
              <div>
                <p className="text-sm font-medium">{t('Xác nhận trước khi chạy lệnh shell')}</p>
              </div>
              <Switch checked={agent.confirm_exec} onChange={(v) => setAgent({ ...agent, confirm_exec: v })} label={t('Xác nhận lệnh shell')} />
            </div>
            <div className="-mx-5 flex items-center justify-between gap-4 border-b border-line/60 px-5 pb-4 last:border-b-0 last:pb-0 col-span-full">
              <p className="text-sm font-medium">{t('Gợi ý tạo kỹ năng từ việc lặp lại')}</p>
              <Switch checked={agent.suggest_habits} onChange={(v) => setAgent({ ...agent, suggest_habits: v })} label={t('Gợi ý kỹ năng')} />
            </div>
          </div>
          <details className="group border-t border-line">
            <summary className="cursor-pointer select-none px-5 py-3 text-sm font-medium text-muted hover:text-fg">{t('Tùy chọn nâng cao')}<span className="ml-2 text-xs font-normal">{t('Mặc định đã ổn, chỉ chỉnh khi bạn biết mình đang làm gì.')}</span></summary>
            <div className="grid gap-4 px-5 pb-5 sm:grid-cols-2">
              <Field label={t('Số bước tối đa mỗi lượt')}><Input type="number" min={1} max={50} value={agent.max_steps} onChange={num('max_steps')} /></Field>
              <Field label={t('Số tin nhắn gửi kèm')}><Input type="number" min={4} max={500} value={agent.max_history} onChange={num('max_history')} /></Field>
              <div className="col-span-full"><Field label={t('Thư mục workspace')}><Input value={agent.workspace} onChange={(e) => setAgent({ ...agent, workspace: e.target.value })} /></Field></div>
              <div className="col-span-full"><Field label={t('Tóm tắt hội thoại khi vượt quá (ký tự)')}><Input type="number" min={4000} step={1000} value={agent.compact_chars} onChange={(e) => setAgent({ ...agent, compact_chars: Number(e.target.value) })} /></Field></div>
            </div>
          </details>
        </Card>
        <Card>
          <CardHeader title="ClawHub" />
          <div className="p-5"><Field label="URL"><Input value={hub} onChange={(e) => setHub(e.target.value)} /></Field></div>
        </Card>
          </>
        )}
        {tab === 'features' && <FeaturesTab value={extra} onChange={setExtra} providers={Object.keys(cfg.data.config.providers)} tools={cfg.data.tools.map((x) => x.name)} />}
        {tab === 'tools' && (
          <>
        <Card>
          <CardHeader title={t('Công cụ')} />
          {cfg.data.tools.map((tool) => (
            <div key={tool.name} className="flex items-center gap-4 border-b border-line px-5 py-3 last:border-b-0">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2"><span className="font-mono text-[13px] font-medium">{tool.name}</span><Badge tone={RISK[tool.risk].tone}>{t(RISK[tool.risk].label)}</Badge></div>
                <p className="text-xs text-muted">{t(tool.description)}</p>
              </div>
              <Switch checked={agent.tools_enabled[tool.name] !== false} onChange={(v) => setAgent({ ...agent, tools_enabled: { ...agent.tools_enabled, [tool.name]: v } })} label={t('Bật tool {name}', { name: tool.name })} />
            </div>
          ))}
        </Card>
          </>
        )}
        {tab === 'security' && (
          <>
        <Card>
          <CardHeader title={t('Sandbox chạy lệnh (Docker)')} />
          <div className="grid gap-4 p-5 sm:grid-cols-2">
            <Field label={t('Chế độ')}><Select value={agent.exec_sandbox} onChange={(e) => setAgent({ ...agent, exec_sandbox: e.target.value as 'none' | 'docker' })}><option value="none">{t('Tắt (chạy trực tiếp trên máy)')}</option><option value="docker">Docker</option></Select></Field>
            <Field label={t('Image')}><Input value={agent.sandbox_image} disabled={agent.exec_sandbox !== 'docker'} onChange={(e) => setAgent({ ...agent, sandbox_image: e.target.value })} className="font-mono" /></Field>
            <div className="-mx-5 flex items-center justify-between gap-4 border-b border-line/60 px-5 pb-4 last:border-b-0 last:pb-0 col-span-full">
              <div><p className="text-sm font-medium">{t('Cho phép container dùng mạng')}</p></div>
              <Switch checked={agent.sandbox_network} onChange={(v) => setAgent({ ...agent, sandbox_network: v })} label={t('Mạng trong sandbox')} disabled={agent.exec_sandbox !== 'docker'} />
            </div>
          </div>
        </Card>
        <PasswordCard has={cfg.data.config.auth.has_password} />
        <SecretsCard s={cfg.data.secrets} />
        <BackupRestoreCard />
          </>
        )}
      </div>
    </Page>
  )
}
