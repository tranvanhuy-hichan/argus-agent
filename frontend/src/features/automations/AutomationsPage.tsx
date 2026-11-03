import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { CircleCheck, CircleX, Pencil, Play, Plus, Timer, Trash2 } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Field, Input, Select, Textarea } from '@/components/ui/Form'
import { Modal } from '@/components/ui/Modal'
import { EmptyState, ErrorNote, Loading, Page, PageHeader } from '@/components/ui/misc'
import { Switch } from '@/components/ui/Switch'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import { useConfig, useJobs } from '@/lib/queries'
import type { Job } from '@/lib/types'
import { errMsg, fmtDateTime, timeAgo } from '@/lib/utils'

const PRESETS: [string, string][] = [
  ['Mỗi giờ', '0 * * * *'], ['Mỗi ngày lúc 8:00', '0 8 * * *'], ['Mỗi ngày lúc 18:00', '0 18 * * *'],
  ['Thứ Hai hàng tuần lúc 9:00', '0 9 * * 1'], ['Mỗi 15 phút', '*/15 * * * *'],
]
const describe = (cron: string) => PRESETS.find(([, c]) => c === cron)?.[0] ?? cron

type Draft = { id?: string; name: string; schedule: string; prompt: string; provider: string | null; enabled: boolean }
const blank: Draft = { name: '', schedule: '0 8 * * *', prompt: '', provider: null, enabled: true }

function JobModal({ draft, onClose }: { draft: Draft | null; onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const cfg = useConfig()
  const [d, setD] = useState<Draft>(blank)
  const [seed, setSeed] = useState<Draft | null>(null)
  if (draft !== seed) { setSeed(draft); if (draft) setD(draft) }
  const save = useMutation({
    mutationFn: () => (d.id ? api.put(`/api/automations/${d.id}`, d) : api.post('/api/automations', d)),
    onSuccess: () => { toast('Đã lưu automation'); void qc.invalidateQueries({ queryKey: ['jobs'] }); onClose() },
    onError: (e) => toast(errMsg(e), 'bad'),
  })
  const isPreset = PRESETS.some(([, c]) => c === d.schedule)
  return (
    <Modal open={!!draft} onClose={onClose} title={d.id ? 'Sửa automation' : 'Tạo automation'}
      footer={<><Button onClick={onClose}>Hủy</Button><Button variant="primary" loading={save.isPending} disabled={!d.name || !d.prompt || !d.schedule} onClick={() => save.mutate()}>Lưu</Button></>}>
      <div className="space-y-4">
        <Field label="Tên"><Input value={d.name} onChange={(e) => setD({ ...d, name: e.target.value })} placeholder="Tóm tắt tin buổi sáng" /></Field>
        <Field label="Lịch chạy">
          <Select value={isPreset ? d.schedule : 'custom'} onChange={(e) => setD({ ...d, schedule: e.target.value === 'custom' ? '' : e.target.value })}>
            {PRESETS.map(([l, c]) => <option key={c} value={c}>{l}</option>)}<option value="custom">Tùy chỉnh (cron)…</option>
          </Select>
        </Field>
        {!isPreset && <Field label="Biểu thức cron" hint="Định dạng: phút giờ ngày tháng thứ. Ví dụ 30 7 * * 1-5 = 7:30 các ngày trong tuần."><Input value={d.schedule} onChange={(e) => setD({ ...d, schedule: e.target.value })} className="font-mono" placeholder="0 8 * * *" /></Field>}
        <Field label="Yêu cầu cho agent" hint="Chạy nền, không có người duyệt nên lệnh shell và file ngoài workspace sẽ bị từ chối."><Textarea rows={5} value={d.prompt} onChange={(e) => setD({ ...d, prompt: e.target.value })} /></Field>
        <Field label="Provider">
          <Select value={d.provider ?? ''} onChange={(e) => setD({ ...d, provider: e.target.value || null })}>
            <option value="">Mặc định</option>{Object.keys(cfg.data?.config.providers ?? {}).map((p) => <option key={p}>{p}</option>)}
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
    onSuccess: () => { toast('Đã bắt đầu chạy, xem kết quả sau ít giây'); setTimeout(() => void refresh(), 8000) },
  })

  return (
    <Page>
      <PageHeader title="Automations" subtitle="Cho agent tự chạy theo lịch, kết quả lưu thành hội thoại riêng." action={<Button variant="primary" onClick={() => setDraft(blank)}><Plus className="size-4" />Tạo automation</Button>} />
      {jobs.isLoading ? <Loading /> : jobs.error ? <ErrorNote error={jobs.error} /> : jobs.data?.length === 0 ? (
        <Card><EmptyState icon={Timer} title="Chưa có automation nào" hint="Ví dụ: mỗi sáng 8h tóm tắt thời tiết, hoặc mỗi tuần kiểm tra dung lượng đĩa." action={<Button variant="primary" onClick={() => setDraft(blank)}><Plus className="size-4" />Tạo automation</Button>} /></Card>
      ) : (
        <div className="space-y-3">
          {jobs.data?.map((j) => (
            <Card key={j.id} className="p-4">
              <div className="flex items-start gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2"><span className="font-medium">{j.name}</span><Badge><Timer className="size-3" />{describe(j.schedule)}</Badge>{j.provider && <Badge>{j.provider}</Badge>}</div>
                  <p className="mt-1 line-clamp-2 text-[13px] text-muted">{j.prompt}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
                    <span>Chạy tới: {j.enabled ? fmtDateTime(j.next_run) : 'đang tắt'}</span>
                    {j.last_run && <span className={j.last_status === 'ok' ? 'text-ok' : 'text-bad'}>{j.last_status === 'ok' ? <CircleCheck className="mr-1 inline size-3.5" /> : <CircleX className="mr-1 inline size-3.5" />}Lần trước {timeAgo(j.last_run)}</span>}
                  </div>
                  {j.last_output && <p className="mt-2 line-clamp-3 rounded-lg bg-bg px-3 py-2 text-xs text-muted">{j.last_output}</p>}
                </div>
                <Switch checked={j.enabled} onChange={() => toggle.mutate(j)} label={`Bật ${j.name}`} />
              </div>
              <div className="mt-3 flex gap-1.5 border-t border-line pt-3">
                <Button size="sm" onClick={() => run.mutate(j.id)}><Play className="size-3.5" />Chạy ngay</Button>
                <Button size="sm" variant="ghost" onClick={() => setDraft({ id: j.id, name: j.name, schedule: j.schedule, prompt: j.prompt, provider: j.provider, enabled: j.enabled })}><Pencil className="size-3.5" />Sửa</Button>
                <Button size="sm" variant="ghost" onClick={() => { if (confirm(`Xóa "${j.name}"?`)) del.mutate(j.id) }}><Trash2 className="size-3.5" />Xóa</Button>
              </div>
            </Card>
          ))}
        </div>
      )}
      <JobModal draft={draft} onClose={() => setDraft(null)} />
    </Page>
  )
}
