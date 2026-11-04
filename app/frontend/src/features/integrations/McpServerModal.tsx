import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { CircleCheck, CircleX, FolderOpen, Globe, Wrench, type LucideIcon } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Field, Input, Select, Textarea } from '@/components/ui/Form'
import { Modal } from '@/components/ui/Modal'
import { Switch } from '@/components/ui/Switch'
import { api } from '@/lib/api'
import type { McpServerCfg } from '@/lib/types'
import { errMsg } from '@/lib/utils'
import { t, tk } from '@/lib/i18n.ts'

export const blankServer: McpServerCfg = { transport: 'stdio', command: '', args: [], env: {}, cwd: '', url: '', headers: {}, oauth: false, oauth_scope: '', enabled: true, confirm: true }

const toLines = (o: Record<string, string>, sep: string) => Object.entries(o).map(([k, v]) => `${k}${sep}${v}`).join('\n')
function fromLines(text: string, sep: string): Record<string, string> {
  const out: Record<string, string> = {}
  for (const line of text.split('\n')) {
    const i = line.indexOf(sep)
    if (i > 0) out[line.slice(0, i).trim()] = line.slice(i + sep.length).trim()
  }
  return out
}

// Dich vu OAuth co san nam o tab "MCP dich vu"; hop thoai nay chi con dung cho dich vu tu them (nhap dia chi MCP)
const PRESETS: Record<string, { name: string; cfg: Partial<McpServerCfg> }> = {
  remote: { name: '', cfg: { transport: 'http', url: '', oauth: true } },
  playwright: { name: 'playwright', cfg: { transport: 'stdio', command: 'npx', args: ['-y', '@playwright/mcp@latest'] } },
  filesystem: { name: 'filesystem', cfg: { transport: 'stdio', command: 'npx', args: ['-y', '@modelcontextprotocol/server-filesystem', tk('/đường/dẫn/thư-mục')] } },
}

type TestResult = { ok: boolean; error?: string; tools?: { name: string; description: string }[] }

export function McpServerModal({ open, name: initialName, initial, onClose, onSave, kind }: {
  open: boolean; name: string | null; initial: McpServerCfg; kind?: 'service'; onClose: () => void; onSave: (name: string, cfg: McpServerCfg) => void
}) {
  const [name, setName] = useState('')
  const [cfg, setCfg] = useState<McpServerCfg>(blankServer)
  const [argsText, setArgsText] = useState('')
  const [envText, setEnvText] = useState('')
  const [headersText, setHeadersText] = useState('')
  const [result, setResult] = useState<TestResult | null>(null)
  const [seed, setSeed] = useState<string | null | undefined>(undefined)
  const [picked, setPicked] = useState<string | null>(null)

  // Nap lai form moi lan mo modal cho mot server khac
  const key = open ? (initialName ?? '') : null
  if (key !== seed) {
    setSeed(key)
    if (open) {
      setName(initialName ?? ''); setCfg(initial); setResult(null)
      if (kind === 'service' && !initialName) { setPicked('remote'); setCfg({ ...blankServer, ...PRESETS.remote.cfg }) } else setPicked(null)
      setArgsText(initial.args.join('\n')); setEnvText(toLines(initial.env, '=')); setHeadersText(toLines(initial.headers, ': '))
    }
  }

  const built = (): McpServerCfg => ({ ...cfg, args: argsText.split('\n').map((a) => a.trim()).filter(Boolean), env: fromLines(envText, '='), headers: fromLines(headersText, ':') })
  const test = useMutation({
    mutationFn: () => api.post<TestResult>('/api/mcp/test', { name: initialName, server: built() }),
    onSuccess: setResult,
    onError: (e) => setResult({ ok: false, error: errMsg(e) }),
  })
  const applyPreset = (id: string) => {
    const p = PRESETS[id]
    if (!p) return
    setName(p.name); setCfg({ ...blankServer, ...p.cfg }); setArgsText((p.cfg.args ?? []).map((a) => t(a)).join('\n')); setResult(null)
  }
  const stdio = cfg.transport === 'stdio'
  const valid = /^[a-z0-9][a-z0-9_-]{0,30}$/.test(name) && (stdio ? cfg.command.trim() : cfg.url.trim())

  const TEMPLATES: { id: string; icon: LucideIcon; label: string; desc: string }[] = [
    { id: 'playwright', icon: Globe, label: t('Duyệt web'), desc: t('Cho agent mở trang web, bấm và điền form (Playwright).') },
    { id: 'filesystem', icon: FolderOpen, label: t('Đọc/ghi file'), desc: t('Cho agent làm việc với file trong một thư mục.') },
    { id: '', icon: Wrench, label: t('Tự cấu hình'), desc: t('Nối một server MCP khác của bạn hoặc của bên thứ ba.') },
  ]
  const showForm = !!initialName || picked !== null

  return (
    <Modal open={open} onClose={() => { setPicked(null); onClose() }} wide title={initialName ? t('Sửa {name}', { name: initialName }) : kind === 'service' ? t('Thêm dịch vụ khác') : t('Thêm công cụ cho agent')}
      footer={showForm ? <><Button onClick={() => { setPicked(null); onClose() }}>{t('Hủy')}</Button><Button variant="primary" disabled={!valid} onClick={() => { onSave(name, built()); setPicked(null) }}>{t('Lưu')}</Button></> : undefined}>
      <div className="space-y-5">
        {!showForm ? (
          <div className="grid gap-3 sm:grid-cols-3">
            {TEMPLATES.map((x) => (
              <button key={x.id || 'custom'} onClick={() => { setPicked(x.id); if (x.id) applyPreset(x.id) }}
                className="flex flex-col gap-1.5 rounded-xl border border-line bg-panel p-4 text-left transition hover:border-accent/60">
                <span className="grid size-9 place-items-center rounded-lg bg-accent/12"><x.icon className="size-5 text-accent" /></span>
                <span className="font-medium">{x.label}</span>
                <span className="text-xs text-muted">{x.desc}</span>
              </button>
            ))}
          </div>
        ) : (
          <>
            <Field label={t('Đặt tên')} hint={t('Chỉ dùng chữ thường, số, - và _. Tên này đứng đầu tên các công cụ (vd. demo__add).')}><Input value={name} disabled={!!initialName} onChange={(e) => setName(e.target.value.toLowerCase())} placeholder="my-project" /></Field>
            {stdio ? (
              <div className="grid gap-4 lg:grid-cols-2">
                <Field label={t('Chương trình cần chạy')}><Input value={cfg.command} onChange={(e) => setCfg({ ...cfg, command: e.target.value })} placeholder={t('/đường/dẫn/python  hoặc  npx')} className="font-mono" /></Field>
                <Field label={t('Tham số (mỗi dòng một tham số)')}><Textarea rows={3} value={argsText} onChange={(e) => setArgsText(e.target.value)} placeholder={t('/đường/dẫn/server.py') + '\n--flag'} /></Field>
              </div>
            ) : (
              <div className="space-y-3">
                <Field label={t('Địa chỉ server (URL)')}><Input value={cfg.url} onChange={(e) => setCfg({ ...cfg, url: e.target.value })} placeholder="http://localhost:8000/mcp" className="font-mono" /></Field>
                <label className="flex items-start gap-3 rounded-lg border border-line bg-panel2 p-3 text-sm">
                  <input type="checkbox" className="mt-1 accent-[var(--accent)]" checked={!!cfg.oauth} onChange={(e) => setCfg({ ...cfg, oauth: e.target.checked })} />
                  <span><span className="font-medium">{t('Đăng nhập bằng tài khoản (OAuth)')}</span></span>
                </label>
              </div>
            )}
            <div className="flex items-start justify-between gap-4 rounded-lg border border-line bg-panel2 p-3">
              <div>
                <p className="text-sm font-medium">{t('Hỏi tôi trước khi dùng công cụ này')}</p>
              </div>
              <Switch checked={cfg.confirm} onChange={(v) => setCfg({ ...cfg, confirm: v })} label={t('Hỏi xác nhận')} />
            </div>
            <details>
              <summary className="cursor-pointer select-none text-sm text-muted hover:text-fg">{t('Tùy chọn nâng cao')}</summary>
              <div className="mt-3 space-y-4">
                <Field label={t('Kiểu kết nối')}>
                  <Select value={cfg.transport} onChange={(e) => setCfg({ ...cfg, transport: e.target.value as McpServerCfg['transport'] })}>
                    <option value="stdio">{t('stdio (chạy lệnh trên máy này)')}</option>
                    <option value="http">HTTP (Streamable HTTP)</option>
                    <option value="sse">{t('SSE (cũ)')}</option>
                  </Select>
                </Field>
                {stdio ? (
                  <div className="grid gap-4 lg:grid-cols-2">
                    <Field label={t('Thư mục chạy (tùy chọn)')}><Input value={cfg.cwd} onChange={(e) => setCfg({ ...cfg, cwd: e.target.value })} className="font-mono" /></Field>
                    <Field label={t('Biến môi trường (KEY=VALUE mỗi dòng)')}><Textarea rows={3} value={envText} onChange={(e) => setEnvText(e.target.value)} /></Field>
                  </div>
                ) : (
                  <Field label={t('Header (Tên: giá trị, mỗi dòng một header)')}><Textarea rows={3} value={headersText} onChange={(e) => setHeadersText(e.target.value)} /></Field>
                )}
              </div>
            </details>
            <div className="flex flex-wrap items-center gap-3">
              {cfg.oauth ? <p className="text-xs text-muted">{t('Máy chủ dùng OAuth không thử được ở đây: bấm Lưu rồi “Đăng nhập” ở danh sách.')}</p> : <Button loading={test.isPending} onClick={() => { setResult(null); test.mutate() }}>{t('Thử kết nối')}</Button>}
              {result && (
                <span className={`flex items-center gap-1.5 text-sm ${result.ok ? 'text-ok' : 'text-bad'}`}>
                  {result.ok ? <CircleCheck className="size-4" /> : <CircleX className="size-4 shrink-0" />}
                  {result.ok ? t('Kết nối được, thấy {n} tool: {names}', { n: result.tools?.length ?? 0, names: result.tools?.map((x) => x.name).join(', ') ?? '' }) : result.error}
                </span>
              )}
            </div>
          </>
        )}
      </div>
    </Modal>
  )
}
