import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { BarChart3, CalendarClock, ChevronDown, Languages, Moon, Newspaper, CircleCheck, CircleX, HeartPulse, Pencil, Play, Plus, Trash2, type LucideIcon } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Field, Input, Select, Textarea } from '@/components/ui/Form'
import { Modal } from '@/components/ui/Modal'
import { ErrorNote, Loading, Page, PageHeader } from '@/components/ui/misc'
import { Switch } from '@/components/ui/Switch'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import { useConfig, useHeartbeat, useJobs } from '@/lib/queries'
import type { Job } from '@/lib/types'
import { cn, errMsg, fmtDateTime, timeAgo } from '@/lib/utils'
import { t, tk } from '@/lib/i18n.ts'
import { T } from '@/lib/T.tsx'
import { build, DAYS, describe, parse, type Freq, type Sched } from './schedule'

const TEMPLATES: { icon: LucideIcon; name: string; prompt: string; schedule: string }[] = [
  { icon: Newspaper, name: tk('Tóm tắt tin buổi sáng'), prompt: tk('Tìm các tin công nghệ nổi bật nhất hôm nay và tóm tắt trong 5 gạch đầu dòng, mỗi ý kèm nguồn.'), schedule: '0 8 * * *' },
  { icon: Moon, name: tk('Nhắc việc cuối ngày'), prompt: tk('Đọc bộ nhớ của bạn về tôi và nhắc những việc còn dang dở cần làm vào ngày mai.'), schedule: '0 18 * * 1-5' },
  { icon: BarChart3, name: tk('Báo cáo cuối tuần'), prompt: tk('Tóm tắt những gì chúng ta đã làm trong tuần qua và gợi ý 3 việc nên ưu tiên tuần tới.'), schedule: '0 17 * * 5' },
  { icon: Languages, name: tk('5 từ tiếng Anh mỗi ngày'), prompt: tk('Gửi tôi 5 từ tiếng Anh hữu ích kèm nghĩa và một câu ví dụ cho mỗi từ.'), schedule: '30 7 * * *' },
]

type Draft = { id?: string; name: string; schedule: string; prompt: string; provider: string | null; enabled: boolean; notify: boolean }
const blank: Draft = { name: '', schedule: '0 8 * * *', prompt: '', provider: null, enabled: true, notify: true }

const FREQS: [Freq, string][] = [[tk('Mỗi ngày'), 'daily'], [tk('Các ngày trong tuần (Thứ Hai – Sáu)'), 'weekdays'], [tk('Một ngày trong tuần'), 'weekly'], [tk('Mỗi giờ'), 'hourly'], [tk('Cứ sau vài phút'), 'minutes'], [tk('Tùy chỉnh (nâng cao)'), 'custom']].map(([l, v]) => [v as Freq, l])

function JobModal({ draft, onClose }: { draft: Draft | null; onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const cfg = useConfig()
  const [d, setD] = useState<Draft>(blank)
  const [sc, setSc] = useState<Sched>(parse(blank.schedule))
  const [seed, setSeed] = useState<Draft | null>(null)
  if (draft !== seed) { setSeed(draft); if (draft) { setD(draft); setSc(parse(draft.schedule)) } }
  const setSched = (patch: Partial<Sched>) => { const n = { ...sc, ...patch }; setSc(n); setD({ ...d, schedule: build(n) }) }
  const save = useMutation({
    mutationFn: () => (d.id ? api.put(`/api/automations/${d.id}`, d) : api.post('/api/automations', d)),
    onSuccess: () => { toast(t('Đã lưu')); void qc.invalidateQueries({ queryKey: ['jobs'] }); onClose() },
    onError: (e) => toast(errMsg(e), 'bad'),
  })
  const needsTime = sc.freq === 'daily' || sc.freq === 'weekdays' || sc.freq === 'weekly'
  return (
    <Modal open={!!draft} onClose={onClose} title={d.id ? t('Sửa việc tự động') : t('Tạo việc tự động')}
      footer={<><Button onClick={onClose}>{t('Hủy')}</Button><Button variant="primary" loading={save.isPending} disabled={!d.name.trim() || !d.prompt.trim() || !d.schedule.trim()} onClick={() => save.mutate()}>{t('Lưu')}</Button></>}>
      <div className="space-y-5">
        <Field label={t('Đặt tên cho việc này')}><Input value={d.name} onChange={(e) => setD({ ...d, name: e.target.value })} placeholder={t('Tóm tắt tin buổi sáng')} /></Field>
        <Field label={t('Mỗi lần chạy, agent cần làm gì?')}>
          <Textarea rows={4} value={d.prompt} onChange={(e) => setD({ ...d, prompt: e.target.value })} />
        </Field>
        <div>
          <p className="mb-1.5 text-sm font-medium">{t('Khi nào chạy?')}</p>
          <div className="grid gap-3 sm:grid-cols-2">
            <Select value={sc.freq} onChange={(e) => setSched({ freq: e.target.value as Freq, cron: build(sc) })} aria-label={t('Tần suất')}>{FREQS.map(([v, l]) => <option key={v} value={v}>{t(l)}</option>)}</Select>
            {needsTime && <Input type="time" value={sc.time} onChange={(e) => setSched({ time: e.target.value || '08:00' })} aria-label={t('Giờ chạy')} />}
            {sc.freq === 'minutes' && <Select value={sc.every} onChange={(e) => setSched({ every: Number(e.target.value) })} aria-label={t('Số phút')}>{[5, 10, 15, 30].map((n) => <option key={n} value={n}>{t('Mỗi {n} phút', { n })}</option>)}</Select>}
            {sc.freq === 'weekly' && <Select value={sc.dow} onChange={(e) => setSched({ dow: Number(e.target.value) })} aria-label={t('Ngày trong tuần')}>{DAYS.map((x, i) => <option key={x} value={i}>{t(x)}</option>)}</Select>}
          </div>
          {sc.freq === 'custom' && <div className="mt-3"><Input value={d.schedule} onChange={(e) => { setD({ ...d, schedule: e.target.value }); setSc({ ...sc, cron: e.target.value }) }} className="font-mono" placeholder="30 7 * * 1-5" aria-label="cron" /><p className="mt-1 text-xs text-muted">{t('Định dạng: phút giờ ngày tháng thứ. Ví dụ 30 7 * * 1-5 = 7:30 các ngày trong tuần.')}</p></div>}
          <p className="mt-2 text-xs text-muted">→ {describe(d.schedule)}</p>
        </div>
        <label className="flex items-start gap-3 rounded-lg border border-line bg-panel2 p-3 text-sm">
          <input type="checkbox" className="mt-1 accent-[var(--accent)]" checked={d.notify} onChange={(e) => setD({ ...d, notify: e.target.checked })} />
          <span><span className="font-medium">{t('Báo kết quả cho tôi')}</span></span>
        </label>
        <details>
          <summary className="cursor-pointer select-none text-sm text-muted hover:text-fg">{t('Tùy chọn nâng cao')}</summary>
          <div className="mt-3"><Field label={t('Dùng mô hình AI nào?')}>
            <Select value={d.provider ?? ''} onChange={(e) => setD({ ...d, provider: e.target.value || null })}>
              <option value="">{t('Mặc định')}</option>{Object.keys(cfg.data?.config.providers ?? {}).map((p) => <option key={p}>{p}</option>)}
            </Select>
          </Field></div>
        </details>
      </div>
    </Modal>
  )
}

function JobCard({ j, onEdit, refresh }: { j: Job; onEdit: () => void; refresh: () => void }) {
  const toast = useToast()
  const [open, setOpen] = useState(false)
  const toggle = useMutation({ mutationFn: () => api.put(`/api/automations/${j.id}`, { ...j, enabled: !j.enabled }), onSuccess: refresh, onError: (e) => toast(errMsg(e), 'bad') })
  const del = useMutation({ mutationFn: () => api.del(`/api/automations/${j.id}`), onSuccess: refresh })
  const run = useMutation({ mutationFn: () => api.post(`/api/automations/${j.id}/run`), onSuccess: () => { toast(t('Đã bắt đầu chạy, xem kết quả sau ít giây')); setTimeout(refresh, 8000) } })
  const ok = j.last_status === 'ok'
  return (
    <Card className={cn(!j.enabled && 'opacity-70')}>
      <div className="flex items-start gap-4 p-4">
        <div className="grid size-10 shrink-0 place-items-center rounded-xl bg-panel2"><CalendarClock className="size-5 text-accent" /></div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2"><span className="font-semibold">{j.name}</span><Badge tone="info">{describe(j.schedule)}</Badge>{j.provider && <Badge>{j.provider}</Badge>}</div>
          <p className="mt-1 line-clamp-2 text-sm text-muted">{j.prompt}</p>
          <p className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
            <span>{j.enabled ? t('Lần tới: {when}', { when: fmtDateTime(j.next_run) }) : t('Đang tạm dừng')}</span>
            {j.last_run && <span className={ok ? 'text-ok' : 'text-bad'}>{ok ? <CircleCheck className="mr-1 inline size-3.5" /> : <CircleX className="mr-1 inline size-3.5" />}{t('Lần trước {ago}', { ago: timeAgo(j.last_run) })}</span>}
          </p>
          {j.last_output && (
            <button onClick={() => setOpen(!open)} className="mt-2 flex w-full items-start gap-1.5 rounded-lg bg-bg px-3 py-2 text-left text-xs text-muted hover:text-fg" aria-expanded={open}>
              <ChevronDown className={cn('mt-0.5 size-3.5 shrink-0 transition', open && 'rotate-180')} />
              <span className={cn('whitespace-pre-wrap', !open && 'line-clamp-2')}>{j.last_output}</span>
            </button>
          )}
        </div>
        <Switch checked={j.enabled} onChange={() => toggle.mutate()} label={t('Bật {name}', { name: j.name })} />
      </div>
      <div className="flex gap-1.5 border-t border-line px-4 py-2.5">
        <Button size="sm" onClick={() => run.mutate()} loading={run.isPending}><Play className="size-3.5" />{t('Chạy thử ngay')}</Button>
        <Button size="sm" variant="ghost" onClick={onEdit}><Pencil className="size-3.5" />{t('Sửa')}</Button>
        <Button size="sm" variant="ghost" onClick={() => { if (confirm(t('Xóa "{name}"?', { name: j.name }))) del.mutate() }}><Trash2 className="size-3.5" />{t('Xóa')}</Button>
      </div>
    </Card>
  )
}

export function AutomationsPage() {
  const jobs = useJobs()
  const qc = useQueryClient()
  const [draft, setDraft] = useState<Draft | null>(null)
  const refresh = () => void qc.invalidateQueries({ queryKey: ['jobs'] })
  const list = jobs.data ?? []
  return (
    <Page>
      <div>
        <PageHeader title={t('Việc tự động theo lịch')}
          action={<Button variant="primary" onClick={() => setDraft(blank)}><Plus className="size-4" />{t('Tạo việc mới')}</Button>} />
        <HeartbeatCard />
        {jobs.isLoading ? <Loading /> : jobs.error ? <ErrorNote error={jobs.error} /> : (
          <>
            {list.length > 0 && <div className="mb-8 grid items-start gap-3 xl:grid-cols-2">{list.map((j) => <JobCard key={j.id} j={j} refresh={refresh} onEdit={() => setDraft({ id: j.id, name: j.name, schedule: j.schedule, prompt: j.prompt, provider: j.provider, enabled: j.enabled, notify: j.notify })} />)}</div>}
            <section>
              <h2 className="text-sm font-semibold">{list.length ? t('Gợi ý thêm') : t('Bắt đầu nhanh với một mẫu')}</h2>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {TEMPLATES.map((x) => (
                  <button key={x.name} onClick={() => setDraft({ ...blank, name: t(x.name), prompt: t(x.prompt), schedule: x.schedule })}
                    className="flex items-start gap-3 rounded-xl border border-line bg-panel p-4 text-left transition hover:border-accent/60">
                    <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-accent/12"><x.icon className="size-5 text-accent" /></span>
                    <span className="min-w-0"><span className="block font-medium">{t(x.name)}</span><span className="mt-0.5 block text-xs text-accent">{describe(x.schedule)}</span><span className="mt-1 line-clamp-2 block text-xs text-muted">{t(x.prompt)}</span></span>
                  </button>
                ))}
              </div>
            </section>
          </>
        )}
        <JobModal draft={draft} onClose={() => setDraft(null)} />
      </div>
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
  const run = useMutation({ mutationFn: () => api.post('/api/heartbeat/run'), onSuccess: () => { toast(t('Đang kiểm tra…')); setTimeout(() => void qc.invalidateQueries({ queryKey: ['heartbeat'] }), 8000) } })
  if (!hb.data || !cfg.data) return null
  const h = hb.data
  const provider = cfg.data.config.heartbeat.provider
  const interval = minutes ?? h.interval_minutes
  const st = { ok: [tk('Không có gì cần báo'), 'text-ok'], alert: [tk('Đã gửi cảnh báo'), 'text-warn'], error: [tk('Lỗi'), 'text-bad'] } as const
  return (
    <Card className="mb-8 p-5">
      <div className="flex items-start gap-4">
        <div className="grid size-10 shrink-0 place-items-center rounded-xl bg-accent/12"><HeartPulse className="size-5 text-accent" /></div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2"><h2 className="font-semibold">{t('Agent tự để mắt giúp bạn')}</h2>{h.running && <Badge tone="info">{t('đang chạy')}</Badge>}</div>
          <p className="mt-0.5 text-sm text-muted"><T k="Cứ {n} phút agent tự xem danh sách trong {file}. Có gì đáng báo thì nhắn bạn (Hộp thư, Telegram), không thì im lặng." v={{ n: interval, file: <Link to="/workspace" className="text-accent hover:underline">HEARTBEAT.md</Link> }} /></p>
          {h.last_run && <p className={`mt-2 text-xs ${st[h.last_status ?? 'ok'][1]}`}>{t('Lần trước {ago}', { ago: timeAgo(h.last_run) })}: {t(st[h.last_status ?? 'ok'][0])}{h.last_output && h.last_status !== 'ok' ? ` — ${h.last_output.slice(0, 160)}` : ''}</p>}
          {h.enabled && h.next_run && <p className="mt-1 text-xs text-muted">{t('Lần tới: {when}', { when: fmtDateTime(h.next_run) })}</p>}
          <details className="mt-3">
            <summary className="cursor-pointer select-none text-xs text-muted hover:text-fg">{t('Tùy chọn')}</summary>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <label className="flex items-center gap-2 text-sm text-muted">{t('Mỗi')}
                <Input type="number" min={5} max={1440} value={interval} onChange={(e) => setMinutes(Number(e.target.value))} onBlur={() => minutes !== null && save.mutate({ enabled: h.enabled, interval_minutes: minutes, provider })} className="w-20" aria-label={t('Phút')} />{t('phút')}</label>
              <Select value={provider ?? ''} onChange={(e) => save.mutate({ enabled: h.enabled, interval_minutes: interval, provider: e.target.value || null })} className="w-48" aria-label={t('Mô hình AI')}>
                <option value="">{t('Mô hình mặc định')}</option>{Object.keys(cfg.data.config.providers).map((p) => <option key={p}>{p}</option>)}</Select>
              <Button size="sm" onClick={() => run.mutate()} loading={run.isPending} disabled={h.running}><Play className="size-3.5" />{t('Kiểm tra thử ngay')}</Button>
            </div>
          </details>
        </div>
        <Switch checked={h.enabled} onChange={(v) => save.mutate({ enabled: v, interval_minutes: interval, provider })} label={t('Bật tự kiểm tra')} />
      </div>
    </Card>
  )
}
