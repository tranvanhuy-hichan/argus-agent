import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Clock, Lightbulb, Puzzle, X } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Field, Input, Textarea } from '@/components/ui/Form'
import { Modal } from '@/components/ui/Modal'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import { t } from '@/lib/i18n.ts'
import { useHabits } from '@/lib/queries'
import type { HabitDraft, HabitSuggestion } from '@/lib/types'
import { errMsg } from '@/lib/utils'

function DraftModal({ s, onClose }: { s: HabitSuggestion; onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [d, setD] = useState<HabitDraft>(s.draft!)
  const set = (patch: Partial<HabitDraft>) => setD({ ...d, ...patch })
  const isAuto = d.kind === 'automation'
  const accept = useMutation({
    mutationFn: () => api.post(`/api/habits/${s.id}/accept`, d),
    onSuccess: () => {
      toast(isAuto ? t('Đã tạo tự động hóa') : t('Đã tạo skill'))
      void qc.invalidateQueries({ queryKey: ['habits'] })
      void qc.invalidateQueries({ queryKey: [isAuto ? 'jobs' : 'skills'] })
      onClose()
    },
    onError: (e) => toast(errMsg(e), 'bad'),
  })
  return (
    <Modal open onClose={onClose} wide title={isAuto ? t('Tạo tự động hóa từ việc lặp lại') : t('Tạo skill từ việc lặp lại')}
      footer={<><Button onClick={onClose}>{t('Hủy')}</Button><Button variant="primary" loading={accept.isPending} disabled={!d.name || (isAuto ? !d.prompt || !d.schedule : !d.body)} onClick={() => accept.mutate()}>{t('Tạo')}</Button></>}>
      <div className="space-y-4">
        <div className="rounded-lg border border-line bg-panel2 p-3 text-xs text-muted">
          <p className="mb-1 font-medium text-fg">{t('Bạn đã gửi {n} lần:', { n: s.count })}</p>
          <ul className="list-disc space-y-0.5 pl-4">{s.examples.slice(0, 3).map((e) => <li key={e} className="truncate">{e}</li>)}</ul>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t('Tên')}><Input value={d.name} onChange={(e) => set({ name: e.target.value })} className="font-mono" /></Field>
          <Field label={t('Loại')}>
            <div className="flex gap-2">
              {(['skill', 'automation'] as const).map((k) => (
                <button key={k} type="button" onClick={() => set({ kind: k, schedule: k === 'automation' && !d.schedule ? '0 8 * * *' : d.schedule, prompt: d.prompt || d.body })}
                  className={`flex-1 rounded-lg border px-3 py-2 text-sm transition ${d.kind === k ? 'border-accent bg-accent/10 text-fg' : 'border-line text-muted hover:text-fg'}`}>
                  {k === 'skill' ? t('Kỹ năng') : t('Tự động hóa')}
                </button>
              ))}
            </div>
          </Field>
        </div>
        {isAuto ? (
          <>
            <Field label={t('Lịch chạy (cron)')}><Input value={d.schedule} onChange={(e) => set({ schedule: e.target.value })} className="font-mono" placeholder="0 8 * * *" /></Field>
            <Field label={t('Lời nhắc')}><Textarea rows={6} value={d.prompt} onChange={(e) => set({ prompt: e.target.value })} /></Field>
          </>
        ) : (
          <>
            <Field label={t('Mô tả (khi nào dùng)')}><Input value={d.description} onChange={(e) => set({ description: e.target.value })} /></Field>
            <Field label={t('Hướng dẫn')}><Textarea rows={8} value={d.body} onChange={(e) => set({ body: e.target.value })} className="font-mono text-xs" /></Field>
          </>
        )}
      </div>
    </Modal>
  )
}

/** Thẻ gợi ý: agent nhận ra một việc lặp lại và đã soạn sẵn bản nháp. */
export function HabitSuggestions() {
  const qc = useQueryClient()
  const habits = useHabits()
  const [open, setOpen] = useState<HabitSuggestion | null>(null)
  const dismiss = useMutation({
    mutationFn: (id: string) => api.post(`/api/habits/${id}/dismiss`, {}),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['habits'] }),
  })
  const list = (habits.data ?? []).filter((h) => h.draft)
  if (!list.length) return null
  return (
    <section className="mb-6 space-y-3" aria-label={t('Gợi ý cho bạn')}>
      {list.map((s) => {
        const auto = s.draft!.kind === 'automation'
        const Icon = auto ? Clock : Puzzle
        return (
          <div key={s.id} className="flex items-center gap-4 rounded-2xl border border-accent/40 bg-accent/5 p-4">
            <div className="grid size-10 shrink-0 place-items-center rounded-xl bg-accent/15 text-accent"><Lightbulb className="size-5" /></div>
            <div className="min-w-0 flex-1">
              <p className="font-medium">{auto ? t('Tạo tự động hóa cho việc này nhé?') : t('Tạo kỹ năng cho việc này nhé?')}</p>
              <p className="mt-0.5 flex items-center gap-1.5 truncate text-sm text-muted"><Icon className="size-3.5 shrink-0" />{s.draft!.title} · {t('đã lặp lại {n} lần', { n: s.count })}</p>
            </div>
            <Button variant="primary" onClick={() => setOpen(s)}>{t('Xem bản nháp')}</Button>
            <button onClick={() => dismiss.mutate(s.id)} aria-label={t('Bỏ qua')} className="rounded-md p-1.5 text-muted hover:bg-panel2 hover:text-fg"><X className="size-4" /></button>
          </div>
        )
      })}
      {open && <DraftModal s={open} onClose={() => setOpen(null)} />}
    </section>
  )
}
