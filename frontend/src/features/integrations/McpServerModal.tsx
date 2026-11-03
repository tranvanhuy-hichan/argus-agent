import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { CircleCheck, CircleX } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Field, Input, Select, Textarea } from '@/components/ui/Form'
import { Modal } from '@/components/ui/Modal'
import { Switch } from '@/components/ui/Switch'
import { api } from '@/lib/api'
import type { McpServerCfg } from '@/lib/types'
import { errMsg } from '@/lib/utils'
import { t, tk } from '@/lib/i18n.ts'

export const blankServer: McpServerCfg = { transport: 'stdio', command: '', args: [], env: {}, cwd: '', url: '', headers: {}, enabled: true, confirm: true }

const toLines = (o: Record<string, string>, sep: string) => Object.entries(o).map(([k, v]) => `${k}${sep}${v}`).join('\n')
function fromLines(text: string, sep: string): Record<string, string> {
  const out: Record<string, string> = {}
  for (const line of text.split('\n')) {
    const i = line.indexOf(sep)
    if (i > 0) out[line.slice(0, i).trim()] = line.slice(i + sep.length).trim()
  }
  return out
}

const PRESETS: Record<string, { name: string; cfg: Partial<McpServerCfg>; note: string }> = {
  playwright: { name: 'playwright', cfg: { transport: 'stdio', command: 'npx', args: ['-y', '@playwright/mcp@latest'] }, note: tk('Điều khiển trình duyệt (cần Node.js). Tải trình duyệt ở lần chạy đầu.') },
  filesystem: { name: 'filesystem', cfg: { transport: 'stdio', command: 'npx', args: ['-y', '@modelcontextprotocol/server-filesystem', tk('/đường/dẫn/thư-mục')] }, note: tk('Đọc/ghi file trong một thư mục (cần Node.js). Nhớ sửa đường dẫn thư mục.') },
}

type TestResult = { ok: boolean; error?: string; tools?: { name: string; description: string }[] }

export function McpServerModal({ open, name: initialName, initial, onClose, onSave }: {
  open: boolean; name: string | null; initial: McpServerCfg; onClose: () => void; onSave: (name: string, cfg: McpServerCfg) => void
}) {
  const [name, setName] = useState('')
  const [cfg, setCfg] = useState<McpServerCfg>(blankServer)
  const [argsText, setArgsText] = useState('')
  const [envText, setEnvText] = useState('')
  const [headersText, setHeadersText] = useState('')
  const [result, setResult] = useState<TestResult | null>(null)
  const [presetNote, setPresetNote] = useState('')
  const [seed, setSeed] = useState<string | null | undefined>(undefined)

  // Nap lai form moi lan mo modal cho mot server khac
  const key = open ? (initialName ?? '') : null
  if (key !== seed) {
    setSeed(key)
    if (open) {
      setName(initialName ?? ''); setCfg(initial); setResult(null); setPresetNote('')
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
    setName(p.name); setCfg({ ...blankServer, ...p.cfg }); setArgsText((p.cfg.args ?? []).map((a) => t(a)).join('\n')); setResult(null); setPresetNote(t(p.note))
  }
  const stdio = cfg.transport === 'stdio'
  const valid = /^[a-z0-9][a-z0-9_-]{0,30}$/.test(name) && (stdio ? cfg.command.trim() : cfg.url.trim())

  return (
    <Modal open={open} onClose={onClose} wide title={initialName ? t('Sửa {name}', { name: initialName }) : t('Thêm MCP server')}
      footer={<><Button onClick={onClose}>{t('Hủy')}</Button><Button variant="primary" disabled={!valid} onClick={() => onSave(name, built())}>{t('Lưu')}</Button></>}>
      <div className="space-y-4">
        {!initialName && (
          <Field label={t('Bắt đầu từ mẫu (tùy chọn)')} hint={presetNote || undefined}>
            <Select value="" onChange={(e) => applyPreset(e.target.value)}><option value="">{t('— Tự cấu hình —')}</option><option value="playwright">{t('Playwright: điều khiển trình duyệt')}</option><option value="filesystem">{t('Filesystem: đọc/ghi file trong thư mục')}</option></Select>
          </Field>
        )}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t('Tên')} hint={t('a-z, 0-9, - và _. Tên này là tiền tố của tool (vd. demo__add).')}><Input value={name} disabled={!!initialName} onChange={(e) => setName(e.target.value.toLowerCase())} placeholder="my-project" /></Field>
          <Field label={t('Kiểu kết nối')}>
            <Select value={cfg.transport} onChange={(e) => setCfg({ ...cfg, transport: e.target.value as McpServerCfg['transport'] })}>
              <option value="stdio">{t('stdio (chạy lệnh trên máy này)')}</option>
              <option value="http">HTTP (Streamable HTTP)</option>
              <option value="sse">{t('SSE (cũ)')}</option>
            </Select>
          </Field>
        </div>
        {stdio ? (
          <>
            <Field label={t('Lệnh (command)')}><Input value={cfg.command} onChange={(e) => setCfg({ ...cfg, command: e.target.value })} placeholder={t('/đường/dẫn/python  hoặc  npx')} className="font-mono" /></Field>
            <Field label={t('Tham số (mỗi dòng một tham số)')}><Textarea rows={3} value={argsText} onChange={(e) => setArgsText(e.target.value)} placeholder={t('/đường/dẫn/server.py') + '\n--flag'} /></Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t('Thư mục chạy (tùy chọn)')}><Input value={cfg.cwd} onChange={(e) => setCfg({ ...cfg, cwd: e.target.value })} className="font-mono" /></Field>
              <Field label={t('Biến môi trường (KEY=VALUE mỗi dòng)')} hint={t('Giá trị đã lưu được che bằng ***, để nguyên nếu không đổi.')}><Textarea rows={3} value={envText} onChange={(e) => setEnvText(e.target.value)} /></Field>
            </div>
          </>
        ) : (
          <>
            <Field label="URL"><Input value={cfg.url} onChange={(e) => setCfg({ ...cfg, url: e.target.value })} placeholder="http://localhost:8000/mcp" className="font-mono" /></Field>
            <Field label={t('Header (Tên: giá trị, mỗi dòng một header)')} hint={t('Dùng cho xác thực, vd. Authorization: Bearer …')}><Textarea rows={3} value={headersText} onChange={(e) => setHeadersText(e.target.value)} /></Field>
          </>
        )}
        <div className="flex items-start justify-between gap-4 rounded-lg border border-line bg-panel2 p-3">
          <div>
            <p className="text-sm font-medium">{t('Hỏi xác nhận trước khi gọi tool')}</p>
            <p className="text-xs text-muted">{t('Tool đánh dấu read-only luôn chạy thẳng. Chỉ tắt với server bạn tin tưởng hoàn toàn.')}</p>
          </div>
          <Switch checked={cfg.confirm} onChange={(v) => setCfg({ ...cfg, confirm: v })} label={t('Hỏi xác nhận')} />
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button loading={test.isPending} onClick={() => { setResult(null); test.mutate() }}>{t('Thử kết nối')}</Button>
          {result && (
            <span className={`flex items-center gap-1.5 text-sm ${result.ok ? 'text-ok' : 'text-bad'}`}>
              {result.ok ? <CircleCheck className="size-4" /> : <CircleX className="size-4 shrink-0" />}
              {result.ok ? t('Kết nối được, thấy {n} tool: {names}', { n: result.tools?.length ?? 0, names: result.tools?.map((x) => x.name).join(', ') ?? '' }) : result.error}
            </span>
          )}
        </div>
      </div>
    </Modal>
  )
}
