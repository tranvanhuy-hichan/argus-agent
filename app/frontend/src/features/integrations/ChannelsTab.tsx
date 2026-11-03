import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CircleCheck, CircleX, Copy, Send, Trash2 } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { Field, Input } from '@/components/ui/Form'
import { ErrorNote, Loading } from '@/components/ui/misc'
import { Switch } from '@/components/ui/Switch'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import type { TelegramStatus } from '@/lib/types'
import { errMsg } from '@/lib/utils'
import { t } from '@/lib/i18n.ts'
import { T } from '@/lib/T.tsx'

export function ChannelsTab() {
  const qc = useQueryClient()
  const toast = useToast()
  const q = useQuery({ queryKey: ['channels'], queryFn: () => api.get<{ telegram: TelegramStatus }>('/api/channels'), refetchInterval: 4000 })
  const [token, setToken] = useState('')
  const [pair, setPair] = useState<string | null>(null)
  const [test, setTest] = useState<{ ok: boolean; text: string } | null>(null)
  const refresh = () => { void qc.invalidateQueries({ queryKey: ['channels'] }) }
  const tg = q.data?.telegram

  const save = useMutation({
    mutationFn: (enabled: boolean) => api.put('/api/channels/telegram', { enabled, token, api_base: tg?.api_base ?? 'https://api.telegram.org' }),
    onSuccess: () => { toast(t('Đã lưu cấu hình Telegram')); setToken(''); refresh() },
    onError: (e) => toast(errMsg(e), 'bad'),
  })
  const doTest = useMutation({
    mutationFn: () => api.post<{ ok: boolean; bot?: string; error?: string }>('/api/channels/telegram/test', { token, api_base: tg?.api_base ?? 'https://api.telegram.org' }),
    onSuccess: (r) => setTest({ ok: r.ok, text: r.ok ? t('Token hợp lệ, bot {bot}', { bot: r.bot ?? '' }) : r.error ?? t('lỗi') }),
  })
  const genCode = useMutation({ mutationFn: () => api.post<{ code: string }>('/api/channels/telegram/pair-code'), onSuccess: (r) => setPair(r.code) })
  const removeUser = useMutation({ mutationFn: (user_id: number) => api.post('/api/channels/telegram/remove-user', { user_id }), onSuccess: refresh })

  if (q.isLoading) return <Loading />
  if (q.error || !tg) return <ErrorNote error={q.error ?? t('không tải được')} />

  return (
    <div className="space-y-4">
      <p className="max-w-3xl text-sm text-muted">{t('Nhắn tin cho agent từ điện thoại. Agent chạy trên máy của bạn và nhận tin bằng long polling, nên không cần mở cổng ra internet.')}</p>
      <Card>
        <CardHeader
          title={<span className="flex items-center gap-2"><Send className="size-4" />Telegram {tg.running ? <Badge tone="ok">{t('Đang chạy {bot}', { bot: tg.bot ?? '' })}</Badge> : tg.enabled ? <Badge tone="bad">{t('Lỗi')}</Badge> : <Badge>{t('Đã tắt')}</Badge>}</span>}
          action={<Switch checked={tg.enabled} onChange={(v) => save.mutate(v)} label={t('Bật Telegram')} disabled={!tg.has_token && !token} />}
        />
        <div className="space-y-4 p-5">
          {tg.error && <p className="rounded-lg border border-bad/30 bg-bad/10 px-3 py-2 font-mono text-xs text-bad">{tg.error}</p>}
          <ol className="list-decimal space-y-1 pl-5 text-sm text-muted">
            <li><T k="Mở Telegram, chat với {bot}, gửi {cmd} và làm theo để nhận token." v={{ bot: <b className="text-fg">@BotFather</b>, cmd: <code className="font-mono">/newbot</code> }} /></li>
            <li><T k="Dán token vào ô bên dưới, bấm {test} rồi {save}." v={{ test: <b className="text-fg">{t('Thử')}</b>, save: <b className="text-fg">{t('Lưu và bật')}</b> }} /></li>
            <li><T k="Bấm {gen}, rồi gửi {cmd} cho bot để cấp quyền cho tài khoản của bạn." v={{ gen: <b className="text-fg">{t('Tạo mã ghép đôi')}</b>, cmd: <code className="font-mono">{t('/pair mã')}</code> }} /></li>
          </ol>
          <Field label={tg.has_token ? t('Token bot (đã lưu, để trống nếu không đổi)') : t('Token bot')}><Input type="password" autoComplete="off" value={token} onChange={(e) => setToken(e.target.value)} placeholder="123456:ABC-DEF…" /></Field>
          <div className="flex flex-wrap items-center gap-3">
            <Button loading={doTest.isPending} disabled={!token && !tg.has_token} onClick={() => { setTest(null); doTest.mutate() }}>{t('Thử')}</Button>
            <Button variant="primary" loading={save.isPending} disabled={!token && !tg.has_token} onClick={() => save.mutate(true)}>{t('Lưu và bật')}</Button>
            {test && <span className={`flex items-center gap-1.5 text-sm ${test.ok ? 'text-ok' : 'text-bad'}`}>{test.ok ? <CircleCheck className="size-4" /> : <CircleX className="size-4" />}{test.text}</span>}
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader title={t('Ghép đôi và quyền truy cập')} hint={t('Chỉ những tài khoản Telegram đã ghép đôi mới giao việc được cho agent.')} action={<Button size="sm" onClick={() => genCode.mutate()} loading={genCode.isPending} disabled={!tg.running}>{t('Tạo mã ghép đôi')}</Button>} />
        <div className="space-y-4 p-5">
          {pair && (
            <div className="flex flex-wrap items-center gap-3 rounded-lg border border-accent/40 bg-accent/5 p-3">
              <span className="font-mono text-2xl font-semibold tracking-widest">{pair}</span>
              <span className="text-sm text-muted"><T k="Gửi {cmd} cho bot trong 10 phút." v={{ cmd: <code className="font-mono text-fg">/pair {pair}</code> }} /></span>
              <button onClick={() => void navigator.clipboard.writeText(`/pair ${pair}`)} aria-label={t('Chép lệnh')} className="ml-auto text-muted hover:text-fg"><Copy className="size-4" /></button>
            </div>
          )}
          {tg.allowed_users.length === 0 ? <p className="text-sm text-muted">{t('Chưa có tài khoản nào được ghép đôi.')}</p> : (
            <ul className="divide-y divide-line rounded-lg border border-line">
              {tg.allowed_users.map((u) => (
                <li key={u} className="flex items-center justify-between px-4 py-2.5 text-sm"><span><T k="ID Telegram {id}" v={{ id: <code className="font-mono">{u}</code> }} /></span>
                  <Button size="sm" variant="ghost" aria-label={t('Gỡ {id}', { id: u })} onClick={() => { if (confirm(t('Gỡ quyền của {id}?', { id: u }))) removeUser.mutate(u) }}><Trash2 className="size-4" /></Button></li>
              ))}
            </ul>
          )}
          <p className="text-xs text-muted"><T k="Lệnh trong Telegram: {new} hội thoại mới, {stop} hủy yêu cầu đang chờ phê duyệt, {id} xem ID của bạn. Khi agent muốn chạy lệnh, bot gửi nút {buttons}; file agent tạo ra được gửi lại kèm theo." v={{ new: <code className="font-mono">/new</code>, stop: <code className="font-mono">/stop</code>, id: <code className="font-mono">/id</code>, buttons: <b>{t('Cho phép')} / {t('Từ chối')}</b> }} /></p>
        </div>
      </Card>
    </div>
  )
}
