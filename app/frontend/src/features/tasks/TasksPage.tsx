import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Check, ChevronDown, CircleCheck, CircleX, Copy, Eye, ListTodo, LoaderCircle, Play, ShieldCheck, Square, Trash2, Zap, type LucideIcon } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Select } from '@/components/ui/Form'
import { ErrorNote, Loading, Page, PageHeader } from '@/components/ui/misc'
import { useToast } from '@/components/ui/Toast'
import { Markdown } from '@/features/chat/Markdown'
import { api } from '@/lib/api'
import { useConfig } from '@/lib/queries'
import type { Task } from '@/lib/types'
import { cn, errMsg, timeAgo } from '@/lib/utils'
import { t, tk } from '@/lib/i18n.ts'

const EXAMPLES = [
  tk('Tìm 5 bài báo mới nhất về trí tuệ nhân tạo và viết tóm tắt vào file tom-tat.md'),
  tk('So sánh 3 cách học tiếng Anh online tốt nhất và lập bảng ưu nhược điểm'),
  tk('Đọc các file trong thư mục làm việc và liệt kê những việc còn dang dở'),
]

const LEVELS: { id: string; icon: LucideIcon; title: string; desc: string }[] = [
  { id: 'readonly', icon: Eye, title: tk('Chỉ xem'), desc: tk('Chỉ đọc và tìm thông tin, không sửa hay tạo gì.') },
  { id: 'default', icon: ShieldCheck, title: tk('Làm việc an toàn'), desc: tk('Được tạo file trong thư mục làm việc. Việc nguy hiểm tự bị từ chối.') },
  { id: 'full', icon: Zap, title: tk('Toàn quyền'), desc: tk('Chạy được cả lệnh trên máy bạn. Chỉ chọn khi bạn tin việc này.') },
]

const active = (s: Task['status']) => s === 'queued' || s === 'running'

function NewTask({ onDone }: { onDone: () => void }) {
  const cfg = useConfig()
  const toast = useToast()
  const [goal, setGoal] = useState('')
  const [role, setRole] = useState('general')
  const [level, setLevel] = useState('default')
  const [more, setMore] = useState(false)
  const start = useMutation({
    mutationFn: () => api.post('/api/tasks', { goal, role, permission: level }),
    onSuccess: () => { toast(t('Agent đã bắt đầu làm. Bạn có thể đóng trang này.')); setGoal(''); onDone() },
    onError: (e) => toast(errMsg(e), 'bad'),
  })
  const roles = Object.entries(cfg.data?.config.agents?.profiles ?? {})
  return (
    <Card className="mb-8 overflow-hidden">
      <div className="p-5 pb-4">
        <label htmlFor="task-goal" className="text-base font-semibold">{t('Bạn muốn agent làm gì?')}</label>
        <textarea id="task-goal" rows={3} value={goal} onChange={(e) => setGoal(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && goal.trim()) start.mutate() }}
          placeholder={t('Ví dụ: tìm 5 bài báo mới nhất về AI và viết tóm tắt vào file')}
          className="w-full resize-none rounded-xl border border-line bg-bg px-4 py-3 text-sm placeholder:text-muted/60 focus:border-accent focus:outline-none" />
        {!goal && (
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="py-1 text-xs text-muted">{t('Gợi ý:')}</span>
            {EXAMPLES.map((x) => <button key={x} onClick={() => setGoal(t(x))} className="rounded-full border border-line px-3 py-1 text-left text-xs text-muted transition hover:border-accent/60 hover:text-fg">{t(x)}</button>)}
          </div>
        )}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line bg-panel2/40 px-5 py-3">
        <button onClick={() => setMore(!more)} className="flex items-center gap-1.5 text-sm text-muted hover:text-fg" aria-expanded={more}>
          <ChevronDown className={cn('size-4 transition', more && 'rotate-180')} />
          {t('Mức tự do:')} <span className="font-medium text-fg">{t(LEVELS.find((l) => l.id === level)!.title)}</span>
        </button>
        <div className="flex items-center gap-3">
          <span className="hidden text-xs text-muted sm:block">Ctrl + Enter</span>
          <Button variant="primary" loading={start.isPending} disabled={!goal.trim()} onClick={() => start.mutate()}><Play className="size-4" />{t('Giao việc')}</Button>
        </div>
      </div>
      {more && (
        <div className="space-y-4 border-t border-line p-5">
          <div>
            <p className="mb-2 text-sm font-medium">{t('Agent được làm gì?')}</p>
            <div className="grid gap-2 sm:grid-cols-3" role="radiogroup">
              {LEVELS.map((l) => (
                <button key={l.id} role="radio" aria-checked={level === l.id} onClick={() => setLevel(l.id)}
                  className={cn('rounded-xl border p-3 text-left transition', level === l.id ? 'border-accent bg-accent/10' : 'border-line hover:border-muted/60')}>
                  <span className="flex items-center gap-2 text-sm font-medium"><l.icon className="size-4 text-accent" />{t(l.title)}</span>
                  <span className="mt-1 block text-xs text-muted">{t(l.desc)}</span>
                </button>
              ))}
            </div>
          </div>
          {roles.length > 0 && (
            <div className="max-w-sm">
              <p className="mb-1.5 text-sm font-medium">{t('Giao cho ai?')}</p>
              <Select value={role} onChange={(e) => setRole(e.target.value)}>
                <option value="general">{t('Agent đa năng')}</option>
                {roles.map(([name, p]) => <option key={name} value={name}>{name}{p.description ? ` — ${p.description}` : ''}</option>)}
              </Select>
            </div>
          )}
        </div>
      )}
    </Card>
  )
}

const dur = (a: number | null, b: number | null) => {
  if (!a || !b) return ''
  const s = Math.max(1, Math.round(b - a))
  return s < 60 ? t('{n} giây', { n: s }) : t('{n} phút', { n: Math.round(s / 60) })
}
const firstLine = (s: string) => s.replace(/[#*`>\-]/g, '').split('\n').map((x) => x.trim()).find(Boolean)?.slice(0, 150) ?? ''

function TaskCard({ task, refresh }: { task: Task; refresh: () => void }) {
  const toast = useToast()
  const [open, setOpen] = useState(false)
  const run = active(task.status)
  const cancel = useMutation({ mutationFn: () => api.post(`/api/tasks/${task.id}/cancel`, {}), onSuccess: refresh, onError: (e) => toast(errMsg(e), 'bad') })
  const del = useMutation({ mutationFn: () => api.del(`/api/tasks/${task.id}`), onSuccess: refresh, onError: (e) => toast(errMsg(e), 'bad') })
  const good = task.status === 'done'
  const stopped = task.status === 'cancelled' || task.status === 'interrupted'
  const pct = task.max_steps ? Math.min(95, Math.max(4, (task.steps / task.max_steps) * 100)) : 8
  const Icon = run ? LoaderCircle : good ? CircleCheck : stopped ? Square : CircleX
  const summary = run ? (task.progress || (task.status === 'queued' ? t('Đang xếp hàng…') : t('Đang bắt đầu…'))) : good ? firstLine(task.result) : (task.error || t('Đã dừng')).slice(0, 150)
  const copy = () => { void navigator.clipboard?.writeText(task.result).then(() => toast(t('Đã chép'))) }
  return (
    <Card className={cn(run && 'border-accent/40')}>
      <div className="flex items-start gap-3 p-4">
        <Icon className={cn('mt-0.5 size-5 shrink-0', run && 'animate-spin text-accent', good && 'text-ok', stopped && 'text-warn', !run && !good && !stopped && 'text-bad')} />
        <button onClick={() => setOpen(!open)} className="min-w-0 flex-1 text-left" aria-expanded={open}>
          <p className="font-medium leading-snug">{task.goal.length > 140 ? task.goal.slice(0, 140) + '…' : task.goal}</p>
          <p className="mt-1 truncate text-sm text-muted">{summary}</p>
          {run && (
            <div className="mt-2.5 flex items-center gap-3">
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-panel2"><div className="h-full rounded-full bg-accent transition-all duration-500" style={{ width: `${pct}%` }} /></div>
              <span className="text-xs tabular-nums text-muted">{t('Bước {n}', { n: task.steps })}</span>
            </div>
          )}
          <p className="mt-1.5 text-xs text-muted/80">
            {task.role && task.role !== 'general' && <span className="mr-2 rounded bg-panel2 px-1.5 py-0.5">{task.role}</span>}
            {task.kind === 'subagent' && <span className="mr-2 rounded bg-panel2 px-1.5 py-0.5">{t('Agent con')}</span>}
            {run ? t('Bắt đầu {ago}', { ago: timeAgo(task.started ?? task.created) }) : `${timeAgo(task.finished ?? task.created)}${dur(task.started, task.finished) ? ` · ${t('mất {d}', { d: dur(task.started, task.finished) })}` : ''}`}
          </p>
        </button>
        {run ? <Button size="sm" onClick={() => cancel.mutate()} loading={cancel.isPending} disabled={task.cancel_requested}><Square className="size-3.5" />{task.cancel_requested ? t('Đang dừng…') : t('Dừng')}</Button>
          : <Button size="sm" variant="ghost" onClick={() => del.mutate()} aria-label={t('Xóa')}><Trash2 className="size-3.5" /></Button>}
      </div>
      {open && (
        <div className="space-y-3 border-t border-line p-4 text-sm">
          {task.error && !good && <p className="rounded-lg border border-bad/30 bg-bad/10 px-3 py-2 text-bad">{task.error}</p>}
          {task.result ? (
            <>
              <div className="max-h-[28rem] overflow-auto rounded-lg bg-bg p-4"><Markdown text={task.result} /></div>
              <div className="flex items-center gap-3">
                <Button size="sm" onClick={copy}><Copy className="size-3.5" />{t('Chép kết quả')}</Button>
                {task.session_id && <Link to={`/chat?session=${task.session_id}`} className="text-xs text-accent hover:underline">{t('Xem agent đã làm thế nào')}</Link>}
              </div>
            </>
          ) : run ? <p className="text-muted">{t('Kết quả sẽ hiện ở đây khi agent làm xong.')}</p> : task.session_id && <Link to={`/chat?session=${task.session_id}`} className="text-xs text-accent hover:underline">{t('Xem agent đã làm thế nào')}</Link>}
        </div>
      )}
    </Card>
  )
}

function Section({ title, count, children }: { title: string; count: number; children: React.ReactNode }) {
  if (!count) return null
  return <section className="mb-6"><h2 className="mb-2.5 flex items-center gap-2 text-sm font-semibold">{title}<span className="rounded-md bg-panel2 px-1.5 py-0.5 text-[11px] font-normal text-muted">{count}</span></h2><div className="grid items-start gap-3 xl:grid-cols-2">{children}</div></section>
}

export function TasksPage() {
  const qc = useQueryClient()
  const [showSub, setShowSub] = useState(false)
  const q = useQuery({ queryKey: ['tasks'], queryFn: () => api.get<Task[]>('/api/tasks'), refetchInterval: (s) => (s.state.data?.some((x) => active(x.status)) ? 1500 : 8000) })
  const refresh = () => void qc.invalidateQueries({ queryKey: ['tasks'] })
  const all = q.data ?? []
  const subs = all.filter((x) => x.kind === 'subagent')
  const mine = all.filter((x) => x.kind !== 'subagent')
  const shown = showSub ? all : mine
  const running = shown.filter((x) => active(x.status))
  const finished = shown.filter((x) => !active(x.status))
  return (
    <Page>
      <div>
        <PageHeader title={t('Giao việc cho agent')} />
        <NewTask onDone={refresh} />
        {q.isLoading ? <Loading /> : q.error ? <ErrorNote error={q.error} /> : (
          <>
            <Section title={t('Đang làm')} count={running.length}>{running.map((x) => <TaskCard key={x.id} task={x} refresh={refresh} />)}</Section>
            <Section title={t('Đã xong')} count={finished.length}>{finished.map((x) => <TaskCard key={x.id} task={x} refresh={refresh} />)}</Section>
            {!shown.length && (
              <div className="rounded-xl border border-dashed border-line py-12 text-center">
                <ListTodo className="mx-auto mb-3 size-8 text-muted" />
                <p className="font-medium">{t('Chưa có việc nào')}</p>
                <p className="mx-auto mt-1 max-w-sm text-sm text-muted">{t('Gõ yêu cầu vào ô phía trên. Hoặc trong Trò chuyện, bạn chỉ cần nói “làm việc này ở chế độ nền giúp tôi”.')}</p>
              </div>
            )}
            {subs.length > 0 && (
              <button onClick={() => setShowSub(!showSub)} className="mt-2 flex items-center gap-1.5 text-xs text-muted hover:text-fg">
                {showSub ? <Check className="size-3.5" /> : <span className="size-3.5 rounded border border-line" />}{t('Hiện cả việc do agent tự giao cho agent con ({n})', { n: subs.length })}
              </button>
            )}
          </>
        )}
      </div>
    </Page>
  )
}
