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

function CopyBlock({ text, label }: { text: string; label?: string }) {
  const [done, setDone] = useState(false)
  return (
    <div className="overflow-hidden rounded-lg border border-line bg-bg">
      <div className="flex items-center justify-between border-b border-line px-3 py-1 text-[11px] text-muted">
        <span>{label ?? ''}</span>
        <button onClick={() => { void navigator.clipboard.writeText(text).then(() => { setDone(true); setTimeout(() => setDone(false), 1500) }) }} className="flex items-center gap-1 hover:text-fg">
          {done ? <Check className="size-3" /> : <Copy className="size-3" />}{done ? 'Đã chép' : 'Chép'}
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
  const revoke = useMutation({ mutationFn: (id: string) => api.del(`/api/tokens/${id}`), onSuccess: () => { toast('Đã thu hồi token'); void qc.invalidateQueries({ queryKey: ['tokens'] }) } })

  if (tokens.isLoading || !info.data) return <Loading />
  if (tokens.error) return <ErrorNote error={tokens.error} />
  const base = window.location.origin
  const tok = fresh ?? 'agt_TOKEN_CỦA_BẠN'
  const curl = `curl -s ${base}/v1/run \\\n  -H "Authorization: Bearer ${tok}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"prompt": "Tóm tắt thư mục workspace", "exec_policy": "deny"}'`
  const py = `import requests\n\nr = requests.post("${base}/v1/run",\n    headers={"Authorization": "Bearer ${tok}"},\n    json={"prompt": "Xin chào", "timeout": 120},\n).json()\nprint(r["output"])`
  const claude = `claude mcp add agent -e AGENT_TOKEN=${tok} -- "${info.data.python}" "${info.data.mcp_server_script}"`
  const generic = JSON.stringify({ mcpServers: { agent: { command: info.data.python, args: [info.data.mcp_server_script], env: { AGENT_TOKEN: tok, AGENT_URL: base } } } }, null, 2)

  return (
    <div className="space-y-4">
      <p className="max-w-3xl text-sm text-muted">Cho phép ứng dụng khác (script, app của bạn, Claude Code, Cursor…) giao việc cho agent này. Mặc định server chỉ nhận kết nối từ chính máy này.</p>

      <Card>
        <CardHeader title="API token" hint="Token chỉ hiện đầy đủ một lần lúc tạo, hệ thống chỉ lưu bản băm." action={<Button variant="primary" size="sm" onClick={() => setCreating(true)}><Plus className="size-4" />Tạo token</Button>} />
        {tokens.data?.length === 0 ? <EmptyState icon={KeyRound} title="Chưa có token nào" hint="Tạo một token để gọi POST /v1/run hoặc đăng ký MCP server." /> : tokens.data?.map((t) => (
          <div key={t.id} className="flex items-center gap-4 border-b border-line px-5 py-3 last:border-b-0">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2"><span className="font-medium">{t.name}</span><code className="font-mono text-xs text-muted">{t.prefix}…</code>{t.allow_exec ? <Badge tone="warn"><ShieldAlert className="size-3" />Được chạy lệnh</Badge> : <Badge tone="ok">Chỉ đọc/hỏi đáp</Badge>}</div>
              <p className="text-xs text-muted">Tạo {timeAgo(t.created)} · dùng lần cuối {t.last_used ? timeAgo(t.last_used) : 'chưa bao giờ'}</p>
            </div>
            <Button size="sm" variant="ghost" aria-label={`Thu hồi ${t.name}`} onClick={() => { if (confirm(`Thu hồi token "${t.name}"? Ứng dụng đang dùng nó sẽ bị từ chối.`)) revoke.mutate(t.id) }}><Trash2 className="size-4" /></Button>
          </div>
        ))}
      </Card>

      <Card>
        <CardHeader title="Cách dùng" hint={fresh ? 'Các ví dụ dưới đây đã điền sẵn token vừa tạo.' : 'Thay agt_TOKEN_CỦA_BẠN bằng token thật.'} />
        <div className="space-y-6 p-5">
          <Section title="1. REST API: POST /v1/run"><CopyBlock label="curl" text={curl} /><CopyBlock label="Python" text={py} /></Section>
          <Section title="2. MCP server (stdio): dùng agent như một tool trong Claude Code, Cursor…">
            <CopyBlock label="Claude Code" text={claude} />
            <CopyBlock label="Cấu hình MCP chung (JSON)" text={generic} />
            <p className="text-xs text-muted">Cung cấp hai tool: <code className="font-mono">agent_run</code> (giao việc, chờ kết quả) và <code className="font-mono">agent_list_skills</code>.</p>
          </Section>
          <Section title="Chính sách chạy lệnh (exec_policy)">
            <p className="text-sm text-muted">App bên ngoài không có người bấm “Cho phép”, nên quyền chạy lệnh do mỗi yêu cầu khai báo và bị giới hạn bởi quyền của token:</p>
            <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
              <li><code className="font-mono text-fg">deny</code> (mặc định): từ chối mọi lệnh shell, tool MCP cần xác nhận và file ngoài workspace.</li>
              <li><code className="font-mono text-fg">allowlist</code> + <code className="font-mono text-fg">exec_allow</code>: chỉ chạy lệnh bắt đầu bằng một mục trong danh sách (vd. <code className="font-mono">["git status", "ls"]</code>), và từ chối lệnh có <code className="font-mono">; &amp; | &lt; &gt; $</code>. Tool MCP: dùng mẫu <code className="font-mono">"mcp:tênserver__*"</code>. Cần token “Được chạy lệnh”.</li>
              <li><code className="font-mono text-fg">allow</code>: cho phép mọi lệnh. Rủi ro cao, chỉ dùng với token và ứng dụng bạn hoàn toàn tin tưởng.</li>
              <li>Tham số <code className="font-mono text-fg">tools</code> giới hạn danh sách tool được phép trong một lượt, <code className="font-mono text-fg">timeout</code> đặt thời gian chờ tối đa.</li>
            </ul>
          </Section>
          <Section title="Dùng từ máy khác">
            <p className="text-sm text-muted">Khởi động với <code className="font-mono text-fg">AGENT_HOST=0.0.0.0 ./run.sh bg</code>. Chỉ các đường <code className="font-mono">/v1/*</code> (có token) nhận kết nối từ xa, còn giao diện web và <code className="font-mono">/api</code> vẫn chỉ mở cho localhost. Nên đặt sau HTTPS (reverse proxy) khi đi qua mạng không tin cậy.</p>
          </Section>
        </div>
      </Card>

      <Modal open={creating} onClose={() => setCreating(false)} title="Tạo API token"
        footer={<><Button onClick={() => setCreating(false)}>Hủy</Button><Button variant="primary" loading={create.isPending} disabled={!name.trim()} onClick={() => create.mutate()}>Tạo</Button></>}>
        <div className="space-y-4">
          <Field label="Tên (để nhớ token dùng cho app nào)"><Input value={name} onChange={(e) => setName(e.target.value)} placeholder="claude-code" /></Field>
          <label className="flex items-start gap-3 rounded-lg border border-line bg-panel2 p-3 text-sm">
            <input type="checkbox" className="mt-1 accent-[var(--accent)]" checked={allowExec} onChange={(e) => setAllowExec(e.target.checked)} />
            <span><span className="font-medium">Cho phép chạy lệnh</span><span className="block text-xs text-muted">Cho phép yêu cầu dùng exec_policy allow/allowlist. Nếu tắt, token chỉ dùng được ở chế độ deny.</span></span>
          </label>
        </div>
      </Modal>
      <Modal open={!!fresh} onClose={() => setFresh(null)} title="Lưu token ngay bây giờ" footer={<Button variant="primary" onClick={() => setFresh(null)}>Tôi đã lưu</Button>}>
        <p className="mb-3 text-sm text-muted">Đây là lần duy nhất token hiện đầy đủ. Nếu mất, bạn phải tạo token mới.</p>
        {fresh && <CopyBlock text={fresh} />}
      </Modal>
    </div>
  )
}
