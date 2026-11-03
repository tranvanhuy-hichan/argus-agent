import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { CircleCheck, CircleX, HeartPulse, Pencil, Play, Plus, Timer, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Field, Input, Select, Textarea } from '@/components/ui/Form'
import { Modal } from '@/components/ui/Modal'
import { EmptyState, ErrorNote, Loading, Page, PageHeader } from '@/components/ui/misc'
import { Switch } from '@/components/ui/Switch'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import { useConfig, useHeartbeat, useJobs } from '@/lib/queries'
import type { Job } from '@/lib/types'
import { errMsg, fmtDateTime, timeAgo } from '@/lib/utils'
import { t, tk } from '@/lib/i18n.ts'
import { T } from '@/lib/T.tsx'

const PRESETS: [string, string][] = [
  [tk('Mỗi giờ'), '0 * * * *'], [tk('Mỗi ngày lúc 8:00'), '0 8 * * *'], [tk('Mỗi ngày lúc 18:00'), '0 18 * * *'],
  [tk('Thứ Hai hàng tuần lúc 9:00'), '0 9 * * 1'], [tk('Mỗi 15 phút'), '*/15 * * * *'],
]
const describe = (cron: string) => { const p = PRESETS.find(([, c]) => c === cron)?.[0]; return p ? t(p) : cron }

type Draft = { id?: string; name: string; schedule: string; prompt: string; provider: string | null; enabled: boolean; notify: boolean }
const blank: Draft = { name: '', schedule: '0 8 * * *', prompt: '', provider: null, enabled: true, notify: true }

function JobModal({ draft, onClose }: { draft: Draft | null; onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const cfg = useConfig()
  const [d, setD] = useState<Draft>(blank)
  const [seed, setSeed] = useState<Draft | null>(null)
  if (draft !== seed) { setSeed(draft); if (draft) setD(draft) }
  const save = useMutation({
    mutationFn: () => (d.id ? api.put(`/api/automations/${d.id}`, d) : api.post('/api/automations', d)),
    onSuccess: () => { toast(t('Đã lưu automation')); void qc.invalidateQueries({ queryKey: ['jobs'] }); onClose() },
    onError: (e) => toast(errMsg(e), 'bad'),
  })
  const isPreset = PRESETS.some(([, c]) => c === d.schedule)
  return (
    <Modal open={!!draft} onClose={onClose} title={d.id ? t('Sửa automation') : t('Tạo automation')}
      footer={<><Button onClick={onClose}>{t('Hủy')}</Button><Button variant="primary" loading={save.isPending} disabled={!d.name || !d.prompt || !d.schedule} onClick={() => save.mutate()}>{t('Lưu')}</Button></>}>
      <div className="space-y-4">
        <Field label={t('Tên')}><Input value={d.name} onChange={(e) => setD({ ...d, name: e.target.value })} placeholder={t('Tóm tắt tin buổi sáng')} /></Field>
        <Field label={t('Lịch chạy')}>
          <Select value={isPreset ? d.schedule : 'custom'} onChange={(e) => setD({ ...d, schedule: e.target.value === 'custom' ? '' : e.target.value })}>
            {PRESETS.map(([l, c]) => <option key={c} value={c}>{t(l)}</option>)}<option value="custom">{t('Tùy chỉnh (cron)…')}</option>
          </Select>
        </Field>
        {!isPreset && <Field label={t('Biểu thức cron')} hint={t('Định dạng: phút giờ ngày tháng thứ. Ví dụ 30 7 * * 1-5 = 7:30 các ngày trong tuần.')}><Input value={d.schedule} onChange={(e) => setD({ ...d, schedule: e.target.value })} className="font-mono" placeholder="0 8 * * *" /></Field>}
        <Field label={t('Yêu cầu cho agent')} hint={t('Chạy nền, không có người duyệt nên lệnh shell và file ngoài workspace sẽ bị từ chối.')}><Textarea rows={5} value={d.prompt} onChange={(e) => setD({ ...d, prompt: e.target.value })} /></Field>
        <label className="flex items-start gap-3 rounded-lg border border-line bg-panel2 p-3 text-sm">
          <input type="checkbox" className="mt-1 accent-[var(--accent)]" checked={d.notify} onChange={(e) => setD({ ...d, notify: e.target.checked })} />
          <span><span className="font-medium">{t('Báo kết quả cho tôi')}</span><span className="block text-xs text-muted">{t('Gửi vào Hộp thư và Telegram (nếu đã kết nối) mỗi khi chạy xong.')}</span></span>
        </label>
        <Field label={t('Nhà cung cấp')}>
          <Select value={d.provider ?? ''} onChange={(e) => setD({ ...d, provider: e.target.value || null })}>
            <option value="">{t('Mặc định')}</option>{Object.keys(cfg.data?.config.providers ?? {}).map((p) => <option key={p}>{p}</option>)}
          </Select>
        </Field>
      </div>
    </Modal>
  )
}

export function AutomationsPage() {
  const jobs = useJobs()
  const qc = useQueryClient()
  const toast = useToast()
  const [draft, setDraft] = useState<Draft | null>(null)
  const refresh = () => qc.invalidateQueries({ queryKey: ['jobs'] })
  const toggle = useMutation({ mutationFn: (j: Job) => api.put(`/api/automations/${j.id}`, { ...j, enabled: !j.enabled }), onSuccess: refresh, onError: (e) => toast(errMsg(e), 'bad') })
  const del = useMutation({ mutationFn: (id: string) => api.del(`/api/automations/${id}`), onSuccess: refresh })
  const run = useMutation({
    mutationFn: (id: string) => api.post(`/api/automations/${id}/run`),
    onSuccess: () => { toast(t('Đã bắt đầu chạy, xem kết quả sau ít giây')); setTimeout(() => void refresh(), 8000) },
  })

  return (
    <Page>
      <PageHeader title={t('Tự động hóa')} subtitle={t('Cho agent tự chạy theo lịch, kết quả lưu thành hội thoại riêng.')} action={<Button variant="primary" onClick={() => setDraft(blank)}><Plus className="size-4" />{t('Tạo automation')}</Button>} />
      <HeartbeatCard />
      {jobs.isLoading ? <Loading /> : jobs.error ? <ErrorNote error={jobs.error} /> : jobs.data?.length === 0 ? (
        <Card><EmptyState icon={Timer} title={t('Chưa có automation nào')} hint={t('Ví dụ: mỗi sáng 8h tóm tắt thời tiết, hoặc mỗi tuần kiểm tra dung lượng đĩa.')} action={<Button variant="primary" onClick={() => setDraft(blank)}><Plus className="size-4" />{t('Tạo automation')}</Button>} /></Card>
      ) : (
        <div className="space-y-3">
          {jobs.data?.map((j) => (
            <Card key={j.id} className="p-4">
              <div className="flex items-start gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2"><span className="font-medium">{j.name}</span><Badge><Timer className="size-3" />{describe(j.schedule)}</Badge>{j.provider && <Badge>{j.provider}</Badge>}</div>
                  <p className="mt-1 line-clamp-2 text-[13px] text-muted">{j.prompt}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
                    <span>{t('Chạy tới: {when}', { when: j.enabled ? fmtDateTime(j.next_run) : t('đang tắt') })}</span>
                    {j.last_run && <span className={j.last_status === 'ok' ? 'text-ok' : 'text-bad'}>{j.last_status === 'ok' ? <CircleCheck className="mr-1 inline size-3.5" /> : <CircleX className="mr-1 inline size-3.5" />}{t('Lần trước {ago}', { ago: timeAgo(j.last_run) })}</span>}
                  </div>
                  {j.last_output && <p className="mt-2 line-clamp-3 rounded-lg bg-bg px-3 py-2 text-xs text-muted">{j.last_output}</p>}
                </div>
                <Switch checked={j.enabled} onChange={() => toggle.mutate(j)} label={t('Bật {name}', { name: j.name })} />
              </div>
              <div className="mt-3 flex gap-1.5 border-t border-line pt-3">
                <Button size="sm" onClick={() => run.mutate(j.id)}><Play className="size-3.5" />{t('Chạy ngay')}</Button>
                <Button size="sm" variant="ghost" onClick={() => setDraft({ id: j.id, name: j.name, schedule: j.schedule, prompt: j.prompt, provider: j.provider, enabled: j.enabled, notify: j.notify })}><Pencil className="size-3.5" />{t('Sửa')}</Button>
                <Button size="sm" variant="ghost" onClick={() => { if (confirm(t('Xóa "{name}"?', { name: j.name }))) del.mutate(j.id) }}><Trash2 className="size-3.5" />{t('Xóa')}</Button>
              </div>
            </Card>
          ))}
        </div>
      )}
      <JobModal draft={draft} onClose={() => setDraft(null)} />
    </Page>
  )
}

export function HeartbeatCard() {
  const hb = useHeartbeat()
  const cfg = useConfig()
  const qc = useQueryClient()
  const toast = useToast()
  const [minutes, setMinutes] = useState<number | null>(null)
  const save = useMutation({
    mutationFn: (v: { enabled: boolean; interval_minutes: number; provider: string | null }) => api.put('/api/heartbeat', v),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ['heartbeat'] }); void qc.invalidateQueries({ queryKey: ['config'] }) },
    onError: (e) => toast(errMsg(e), 'bad'),
  })
  const run = useMutation({ mutationFn: () => api.post('/api/heartbeat/run'), onSuccess: () => { toast(t('Đang chạy heartbeat…')); setTimeout(() => void qc.invalidateQueries({ queryKey: ['heartbeat'] }), 8000) } })
  if (!hb.data || !cfg.data) return null
  const h = hb.data
  const provider = cfg.data.config.heartbeat.provider
  const interval = minutes ?? h.interval_minutes
  const st = { ok: [tk('Không có gì cần báo'), 'text-ok'], alert: [tk('Đã gửi cảnh báo'), 'text-warn'], error: [tk('Lỗi'), 'text-bad'] } as const
  return (
    <Card className="mb-6 p-5">
      <div className="flex items-start gap-4">
        <div className="grid size-10 shrink-0 place-items-center rounded-xl bg-panel2"><HeartPulse className="size-5 text-accent" /></div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2"><h2 className="font-semibold">Heartbeat</h2>{h.running && <Badge tone="info">{t('đang chạy')}</Badge>}</div>
          <p className="mt-0.5 text-sm text-muted"><T k="Định kỳ agent tự đọc {file} và làm theo danh sách việc. Nếu có điều đáng báo, nó chủ động nhắn bạn (Hộp thư, Telegram); nếu không, im lặng." v={{ file: <Link to="/workspace" className="text-accent hover:underline">HEARTBEAT.md</Link> }} /></p>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2 text-sm text-muted">{t('Mỗi')}
              <Input type="number" min={5} max={1440} value={interval} onChange={(e) => setMinutes(Number(e.target.value))} onBlur={() => minutes !== null && save.mutate({ enabled: h.enabled, interval_minutes: minutes, provider })} className="w-20" aria-label={t('Phút')} />{t('phút')}</label>
            <Select value={provider ?? ''} onChange={(e) => save.mutate({ enabled: h.enabled, interval_minutes: interval, provider: e.target.value || null })} className="w-48" aria-label={t('Nhà cung cấp heartbeat')}>
              <option value="">{t('Nhà cung cấp mặc định')}</option>{Object.keys(cfg.data.config.providers).map((p) => <option key={p}>{p}</option>)}</Select>
            <Button size="sm" onClick={() => run.mutate()} loading={run.isPending} disabled={h.running}><Play className="size-3.5" />{t('Chạy thử')}</Button>
          </div>
          {h.last_run && <p className={`mt-3 text-xs ${st[h.last_status ?? 'ok'][1]}`}>{t('Lần trước {ago}', { ago: timeAgo(h.last_run) })}: {t(st[h.last_status ?? 'ok'][0])}{h.last_output && h.last_status !== 'ok' ? ` — ${h.last_output.slice(0, 160)}` : ''}</p>}
          {h.enabled && h.next_run && <p className="mt-1 text-xs text-muted">{t('Lần tới: {when}', { when: fmtDateTime(h.next_run) })}</p>}
        </div>
        <Switch checked={h.enabled} onChange={(v) => save.mutate({ enabled: v, interval_minutes: interval, provider })} label={t('Bật heartbeat')} />
      </div>
    </Card>
  )
}
