import { useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Copy, KeyRound, Plus, ShieldAlert, Trash2 } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { Field, Input } from '@/components/ui/Form'
import { Modal } from '@/components/ui/Modal'
import { EmptyState, ErrorNote, Loading } from '@/components/ui/misc'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import { useTokens } from '@/lib/queries'
import { errMsg, timeAgo } from '@/lib/utils'
import { t } from '@/lib/i18n.ts'
import { T } from '@/lib/T.tsx'

function CopyBlock({ text, label }: { text: string; label?: string }) {
  const [done, setDone] = useState(false)
  return (
    <div className="overflow-hidden rounded-lg border border-line bg-bg">
      <div className="flex items-center justify-between border-b border-line px-3 py-1 text-[11px] text-muted">
        <span>{label ?? ''}</span>
        <button onClick={() => { void navigator.clipboard.writeText(text).then(() => { setDone(true); setTimeout(() => setDone(false), 1500) }) }} className="flex items-center gap-1 hover:text-fg">
          {done ? <Check className="size-3" /> : <Copy className="size-3" />}{done ? t('Đã chép') : t('Chép')}
        </button>
      </div>
      <pre className="overflow-x-auto p-3 font-mono text-[12.5px] leading-relaxed">{text}</pre>
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return <section className="space-y-2"><h3 className="text-sm font-semibold">{title}</h3>{children}</section>
}

export function ApiTab() {
  const tokens = useTokens()
  const info = useQuery({ queryKey: ['integration-info'], queryFn: () => api.get<{ python: string; mcp_server_script: string }>('/api/integration-info') })
  const qc = useQueryClient()
  const toast = useToast()
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [allowExec, setAllowExec] = useState(false)
  const [fresh, setFresh] = useState<string | null>(null)

  const create = useMutation({
    mutationFn: () => api.post<{ token: string }>('/api/tokens', { name, allow_exec: allowExec }),
    onSuccess: (r) => { setFresh(r.token); setCreating(false); setName(''); setAllowExec(false); void qc.invalidateQueries({ queryKey: ['tokens'] }) },
    onError: (e) => toast(errMsg(e), 'bad'),
  })
  const revoke = useMutation({ mutationFn: (id: string) => api.del(`/api/tokens/${id}`), onSuccess: () => { toast(t('Đã thu hồi token')); void qc.invalidateQueries({ queryKey: ['tokens'] }) } })

  if (tokens.isLoading || !info.data) return <Loading />
  if (tokens.error) return <ErrorNote error={tokens.error} />
  const base = window.location.origin
  const tok = fresh ?? t('agt_TOKEN_CỦA_BẠN')
  const curl = `curl -s ${base}/v1/run \\\n  -H "Authorization: Bearer ${tok}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"prompt": "${t('Tóm tắt thư mục workspace')}", "exec_policy": "deny"}'`
  const py = `import requests\n\nr = requests.post("${base}/v1/run",\n    headers={"Authorization": "Bearer ${tok}"},\n    json={"prompt": "${t('Xin chào')}", "timeout": 120},\n).json()\nprint(r["output"])`
  const claude = `claude mcp add argus -e ARGUS_TOKEN=${tok} -- "${info.data.python}" "${info.data.mcp_server_script}"`
  const generic = JSON.stringify({ mcpServers: { argus: { command: info.data.python, args: [info.data.mcp_server_script], env: { ARGUS_TOKEN: tok, ARGUS_URL: base } } } }, null, 2)

  return (
    <div className="space-y-4">
      <p className="max-w-3xl text-sm text-muted">{t('Cho phép ứng dụng khác (script, app của bạn, Claude Code, Cursor…) giao việc cho agent này. Mặc định server chỉ nhận kết nối từ chính máy này.')}</p>

      <Card>
        <CardHeader title={t('API token')} hint={t('Token chỉ hiện đầy đủ một lần lúc tạo, hệ thống chỉ lưu bản băm.')} action={<Button variant="primary" size="sm" onClick={() => setCreating(true)}><Plus className="size-4" />{t('Tạo token')}</Button>} />
        {tokens.data?.length === 0 ? <EmptyState icon={KeyRound} title={t('Chưa có token nào')} hint={t('Tạo một token để gọi POST /v1/run hoặc đăng ký MCP server.')} /> : tokens.data?.map((tk) => (
          <div key={tk.id} className="flex items-center gap-4 border-b border-line px-5 py-3 last:border-b-0">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2"><span className="font-medium">{tk.name}</span><code className="font-mono text-xs text-muted">{tk.prefix}…</code>{tk.allow_exec ? <Badge tone="warn"><ShieldAlert className="size-3" />{t('Được chạy lệnh')}</Badge> : <Badge tone="ok">{t('Chỉ đọc/hỏi đáp')}</Badge>}</div>
              <p className="text-xs text-muted">{t('Tạo {ago} · dùng lần cuối {last}', { ago: timeAgo(tk.created), last: tk.last_used ? timeAgo(tk.last_used) : t('chưa bao giờ') })}</p>
            </div>
            <Button size="sm" variant="ghost" aria-label={t('Thu hồi {name}', { name: tk.name })} onClick={() => { if (confirm(t('Thu hồi token "{name}"? Ứng dụng đang dùng nó sẽ bị từ chối.', { name: tk.name }))) revoke.mutate(tk.id) }}><Trash2 className="size-4" /></Button>
          </div>
        ))}
      </Card>

      <Card>
        <CardHeader title={t('Cách dùng')} hint={fresh ? t('Các ví dụ dưới đây đã điền sẵn token vừa tạo.') : t('Thay {ph} bằng token thật.', { ph: t('agt_TOKEN_CỦA_BẠN') })} />
        <div className="space-y-6 p-5">
          <Section title={t('1. REST API: POST /v1/run')}><CopyBlock label="curl" text={curl} /><CopyBlock label="Python" text={py} /></Section>
          <Section title={t('2. MCP server (stdio): dùng agent như một tool trong Claude Code, Cursor…')}>
            <CopyBlock label="Claude Code" text={claude} />
            <CopyBlock label={t('Cấu hình MCP chung (JSON)')} text={generic} />
            <p className="text-xs text-muted"><T k="Cung cấp hai tool: {run} (giao việc, chờ kết quả) và {list}." v={{ run: <code className="font-mono">agent_run</code>, list: <code className="font-mono">agent_list_skills</code> }} /></p>
          </Section>
          <Section title={t('Chính sách chạy lệnh (exec_policy)')}>
            <p className="text-sm text-muted">{t('App bên ngoài không có người bấm “Cho phép”, nên quyền chạy lệnh do mỗi yêu cầu khai báo và bị giới hạn bởi quyền của token:')}</p>
            <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
              <li><T k="{p} (mặc định): từ chối mọi lệnh shell, tool MCP cần xác nhận và file ngoài workspace." v={{ p: <code className="font-mono text-fg">deny</code> }} /></li>
              <li><T k="{a} + {b}: chỉ chạy lệnh bắt đầu bằng một mục trong danh sách (vd. {ex}), và từ chối lệnh có {chars}. Tool MCP: dùng mẫu {pat}. Cần token “Được chạy lệnh”." v={{ a: <code className="font-mono text-fg">allowlist</code>, b: <code className="font-mono text-fg">exec_allow</code>, ex: <code className="font-mono">["git status", "ls"]</code>, chars: <code className="font-mono">; &amp; | &lt; &gt; $</code>, pat: <code className="font-mono">"mcp:{t('tênserver')}__*"</code> }} /></li>
              <li><T k="{p}: cho phép mọi lệnh. Rủi ro cao, chỉ dùng với token và ứng dụng bạn hoàn toàn tin tưởng." v={{ p: <code className="font-mono text-fg">allow</code> }} /></li>
              <li><T k="Tham số {tools} giới hạn danh sách tool được phép trong một lượt, {timeout} đặt thời gian chờ tối đa." v={{ tools: <code className="font-mono text-fg">tools</code>, timeout: <code className="font-mono text-fg">timeout</code> }} /></li>
            </ul>
          </Section>
          <Section title={t('Dùng từ máy khác')}>
            <p className="text-sm text-muted"><T k="Khởi động với {cmd}. Chỉ các đường {v1} (có token) nhận kết nối từ xa, còn giao diện web và {api} vẫn chỉ mở cho localhost. Nên đặt sau HTTPS (reverse proxy) khi đi qua mạng không tin cậy." v={{ cmd: <code className="font-mono text-fg">argus start --host 0.0.0.0</code>, v1: <code className="font-mono">/v1/*</code>, api: <code className="font-mono">/api</code> }} /></p>
          </Section>
        </div>
      </Card>

      <Modal open={creating} onClose={() => setCreating(false)} title={t('Tạo API token')}
        footer={<><Button onClick={() => setCreating(false)}>{t('Hủy')}</Button><Button variant="primary" loading={create.isPending} disabled={!name.trim()} onClick={() => create.mutate()}>{t('Tạo')}</Button></>}>
        <div className="space-y-4">
          <Field label={t('Tên (để nhớ token dùng cho app nào)')}><Input value={name} onChange={(e) => setName(e.target.value)} placeholder="claude-code" /></Field>
          <label className="flex items-start gap-3 rounded-lg border border-line bg-panel2 p-3 text-sm">
            <input type="checkbox" className="mt-1 accent-[var(--accent)]" checked={allowExec} onChange={(e) => setAllowExec(e.target.checked)} />
            <span><span className="font-medium">{t('Cho phép chạy lệnh')}</span><span className="block text-xs text-muted">{t('Cho phép yêu cầu dùng exec_policy allow/allowlist. Nếu tắt, token chỉ dùng được ở chế độ deny.')}</span></span>
          </label>
        </div>
      </Modal>
      <Modal open={!!fresh} onClose={() => setFresh(null)} title={t('Lưu token ngay bây giờ')} footer={<Button variant="primary" onClick={() => setFresh(null)}>{t('Tôi đã lưu')}</Button>}>
        <p className="mb-3 text-sm text-muted">{t('Đây là lần duy nhất token hiện đầy đủ. Nếu mất, bạn phải tạo token mới.')}</p>
        {fresh && <CopyBlock text={fresh} />}
      </Modal>
    </div>
  )
}
