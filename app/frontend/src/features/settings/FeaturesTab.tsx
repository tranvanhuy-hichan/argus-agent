import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Brain } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { Field, Input, Select } from '@/components/ui/Form'
import { Switch } from '@/components/ui/Switch'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import type { ExtraCfg, MemoryStatus } from '@/lib/types'
import { errMsg } from '@/lib/utils'
import { t } from '@/lib/i18n.ts'

function Row({ title, children }: { title: string; children: React.ReactNode }) {
  return <div className="flex items-center justify-between gap-4 sm:col-span-2"><p className="text-sm font-medium">{title}</p>{children}</div>
}

function MemoryStatusLine() {
  const qc = useQueryClient()
  const toast = useToast()
  const q = useQuery({ queryKey: ['memory-status'], queryFn: () => api.get<MemoryStatus>('/api/memory/status'), refetchInterval: (s) => (s.state.data?.reindex.running ? 1500 : false) })
  const re = useMutation({ mutationFn: () => api.post('/api/memory/reindex', {}), onSuccess: () => void qc.invalidateQueries({ queryKey: ['memory-status'] }), onError: (e) => toast(errMsg(e), 'bad') })
  const d = q.data
  if (!d) return null
  const e = d.embedding
  return (
    <div className="space-y-2 rounded-lg border border-line bg-panel2 p-3 text-xs sm:col-span-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-muted">{t('Đang dùng:')}</span><span className="font-mono">{e.model_id ?? t('tắt')}</span>
        {e.backend && (e.reachable ? <Badge tone="ok">{t('kết nối được')}</Badge> : <Badge tone="bad">{t('không kết nối được')}</Badge>)}
        <span className="text-muted">{t('{n} đoạn đã lập chỉ mục', { n: d.vectors.total })}</span>
      </div>
      {e.error && <p className="text-bad">{e.error}</p>}
      <div className="flex items-center gap-3">
        <Button size="sm" onClick={() => re.mutate()} loading={re.isPending || d.reindex.running}><Brain className="size-3.5" />{t('Lập lại chỉ mục')}</Button>
        {d.reindex.running && <span className="text-muted">{d.reindex.done}/{d.reindex.total}</span>}
        <span className="text-muted">{t('Cần chạy lại sau khi đổi model embedding.')}</span>
      </div>
    </div>
  )
}

export function FeaturesTab({ value, onChange, providers, tools }: { value: ExtraCfg; onChange: (v: ExtraCfg) => void; providers: string[]; tools: string[] }) {
  const set = <K extends keyof ExtraCfg>(k: K, patch: Partial<ExtraCfg[K]>) => onChange({ ...value, [k]: { ...value[k], ...patch } })
  const provOpts = (blank: string) => <><option value="">{blank}</option>{providers.map((p) => <option key={p} value={p}>{p}</option>)}</>
  const { browser, memory, media, computer, agents } = value
  return (
    <>
      <Card>
        <CardHeader title={t('Trình duyệt')} />
        <div className="grid gap-4 p-5 sm:grid-cols-2">
          <Row title={t('Bật điều khiển trình duyệt')}><Switch checked={browser.enabled} onChange={(v) => set('browser', { enabled: v })} label={t('Bật trình duyệt')} /></Row>
          <Row title={t('Chạy ẩn (không hiện cửa sổ)')}><Switch checked={browser.headless} onChange={(v) => set('browser', { headless: v })} label={t('Chạy ẩn')} disabled={!browser.enabled} /></Row>
          <Row title={t('Cho phép mở địa chỉ nội bộ')}><Switch checked={browser.allow_private} onChange={(v) => set('browser', { allow_private: v })} label={t('Cho phép địa chỉ nội bộ')} disabled={!browser.enabled} /></Row>
          <Field label={t('Đường dẫn Chromium/Chrome')}><Input value={browser.executable} className="font-mono" onChange={(e) => set('browser', { executable: e.target.value })} /></Field>
          <Field label={t('Tự đóng sau (phút không dùng)')}><Input type="number" min={1} max={240} value={browser.idle_minutes} onChange={(e) => set('browser', { idle_minutes: Number(e.target.value) })} /></Field>
        </div>
      </Card>

      <Card>
        <CardHeader title={t('Trí nhớ theo nghĩa')} />
        <div className="grid gap-4 p-5 sm:grid-cols-2">
          <Field label={t('Embedding')}>
            <Select value={memory.embeddings} onChange={(e) => set('memory', { embeddings: e.target.value as ExtraCfg['memory']['embeddings'] })}>
              <option value="auto">{t('Tự chọn')}</option><option value="hash">hash ({t('không cần model')})</option><option value="ollama">Ollama</option><option value="openai">{t('API tương thích OpenAI (Gemini, OpenAI…)')}</option><option value="off">{t('Tắt')}</option>
            </Select>
          </Field>
          <Field label={t('Provider')}><Select value={memory.provider ?? ''} onChange={(e) => set('memory', { provider: e.target.value || null })} disabled={memory.embeddings === 'off' || memory.embeddings === 'hash'}>{provOpts(t('Tự chọn'))}</Select></Field>
          <Field label={t('Model embedding')}><Input value={memory.model} className="font-mono" onChange={(e) => set('memory', { model: e.target.value })} /></Field>
          <Row title={t('Tự lập chỉ mục tin nhắn mới')}><Switch checked={memory.auto_index} onChange={(v) => set('memory', { auto_index: v })} label={t('Tự lập chỉ mục')} /></Row>
          <MemoryStatusLine />
        </div>
      </Card>

      <Card>
        <CardHeader title={t('Ảnh và hình ảnh')} />
        <div className="grid gap-4 p-5 sm:grid-cols-3">
          <Field label={t('Provider tạo ảnh')}><Select value={media.image_provider ?? ''} onChange={(e) => set('media', { image_provider: e.target.value || null })}>{provOpts(t('Chưa chọn'))}</Select></Field>
          <Field label={t('Model tạo ảnh')}><Input value={media.image_model} className="font-mono" onChange={(e) => set('media', { image_model: e.target.value })} /></Field>
          <Field label={t('Provider để xem ảnh')}><Select value={media.vision_provider ?? ''} onChange={(e) => set('media', { vision_provider: e.target.value || null })}>{provOpts(t('Tự chọn'))}</Select></Field>
        </div>
      </Card>

      <Card>
        <CardHeader title={t('Điều khiển máy tính')} />
        <div className="space-y-3 p-5">
          <Row title={t('Bật điều khiển máy tính')}><Switch checked={computer.enabled} onChange={(v) => set('computer', { enabled: v })} label={t('Bật điều khiển máy tính')} /></Row>
          {computer.enabled && <p className="rounded-lg border border-warn/40 bg-warn/10 px-3 py-2 text-sm text-warn">{t('Cẩn thận: agent có thể bấm vào bất cứ thứ gì trên màn hình, kể cả cửa sổ chứa mật khẩu. Chỉ bật khi bạn ngồi canh, và đừng để ở chế độ Toàn quyền khi vắng mặt. Trên Linux cần xdotool (X11) hoặc ydotool + wtype (Wayland).')}</p>}
        </div>
      </Card>

      <Card>
        <CardHeader title={t('Agent con và việc dài')} />
        <div className="grid gap-4 p-5 sm:grid-cols-3">
          <Field label={t('Độ sâu tối đa')}><Input type="number" min={0} max={4} value={agents.max_depth} onChange={(e) => set('agents', { max_depth: Number(e.target.value) })} /></Field>
          <Field label={t('Chạy song song')}><Input type="number" min={1} max={8} value={agents.max_parallel} onChange={(e) => set('agents', { max_parallel: Number(e.target.value) })} /></Field>
          <Field label={t('Bước tối đa cho việc nền')}><Input type="number" min={5} max={200} value={agents.task_max_steps} onChange={(e) => set('agents', { task_max_steps: Number(e.target.value) })} /></Field>
        </div>
        <details className="border-t border-line">
          <summary className="cursor-pointer select-none px-5 py-3 text-sm font-medium text-muted hover:text-fg">{t('Vai trò của agent con')}</summary>
          {Object.entries(agents.profiles).map(([name, p]) => (
            <div key={name} className="space-y-2 border-b border-line px-5 py-3 last:border-b-0">
              <div className="flex items-center gap-2"><span className="font-mono text-[13px] font-medium">{name}</span><span className="text-xs text-muted">{p.description}</span></div>
              <div className="grid gap-3 sm:grid-cols-3">
                <Field label={t('Provider')}><Select value={p.provider ?? ''} onChange={(e) => onChange({ ...value, agents: { ...agents, profiles: { ...agents.profiles, [name]: { ...p, provider: e.target.value || null } } } })}>{provOpts(t('Mặc định'))}</Select></Field>
                <Field label={t('Bước tối đa')}><Input type="number" min={1} max={100} value={p.max_steps} onChange={(e) => onChange({ ...value, agents: { ...agents, profiles: { ...agents.profiles, [name]: { ...p, max_steps: Number(e.target.value) } } } })} /></Field>
                <Field label={t('Tool được dùng')}><Input value={p.tools.join(', ')} className="font-mono" placeholder={tools.slice(0, 3).join(', ')}
                  onChange={(e) => onChange({ ...value, agents: { ...agents, profiles: { ...agents.profiles, [name]: { ...p, tools: e.target.value.split(',').map((x) => x.trim()).filter(Boolean) } } } })} /></Field>
              </div>
            </div>
          ))}
        </details>
      </Card>
    </>
  )
}
