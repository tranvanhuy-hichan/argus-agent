import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Bell, CheckCheck, Filter, Trash2 } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { EmptyState, ErrorNote, Loading, Page, PageHeader } from '@/components/ui/misc'
import { api } from '@/lib/api'
import type { NotificationItem } from '@/lib/types'
import { cn, timeAgo } from '@/lib/utils'
import { t } from '@/lib/i18n.ts'

type FilterType = 'all' | 'unread' | 'heartbeat' | 'cron' | 'task'

export function NotificationsPage() {
  const qc = useQueryClient()
  const [filter, setFilter] = useState<FilterType>('all')
  const q = useQuery({ queryKey: ['notifications'], queryFn: () => api.get<{ items: NotificationItem[]; unread: number }>('/api/notifications'), refetchInterval: 10_000 })
  const refresh = () => { void qc.invalidateQueries({ queryKey: ['notifications'] }); void qc.invalidateQueries({ queryKey: ['notif-count'] }) }
  const readAll = useMutation({ mutationFn: () => api.post('/api/notifications/read', {}), onSuccess: refresh })
  const readOne = useMutation({ mutationFn: (id: number) => api.post('/api/notifications/read', { ids: [id] }), onSuccess: refresh })
  const clear = useMutation({ mutationFn: () => api.del('/api/notifications'), onSuccess: refresh })

  const items = q.data?.items ?? []
  const filtered = items.filter((n) => {
    if (filter === 'unread') return !n.read
    if (filter === 'heartbeat') return n.source === 'heartbeat'
    if (filter === 'cron') return n.source === 'cron'
    if (filter === 'task') return n.source === 'task' || n.source === 'job'
    return true
  })

  return (
    <Page>
      <PageHeader title={t('Hộp thư')}
        action={<div className="flex gap-2"><Button onClick={() => readAll.mutate()} disabled={!q.data?.unread}><CheckCheck className="size-4" />{t('Đánh dấu đã đọc')}</Button><Button variant="danger" onClick={() => { if (confirm(t('Xóa toàn bộ thông báo?'))) clear.mutate() }} disabled={!q.data?.items.length}><Trash2 className="size-4" />{t('Xóa hết')}</Button></div>} />
      
      {/* Thanh bộ lọc */}
      {items.length > 0 && (
        <div className="mb-4 flex flex-wrap items-center gap-1.5 text-xs text-muted">
          <Filter className="size-3.5" />
          <span>{t('Lọc theo:')}</span>
          {[
            { id: 'all', label: t('Tất cả ({n})', { n: items.length }) },
            { id: 'unread', label: t('Chưa đọc ({n})', { n: q.data?.unread ?? 0 }) },
            { id: 'heartbeat', label: 'Heartbeat' },
            { id: 'cron', label: t('Tự động hóa') },
            { id: 'task', label: t('Tác vụ') },
          ].map((item) => (
            <button
              key={item.id}
              onClick={() => setFilter(item.id as FilterType)}
              className={cn(
                'rounded-lg px-2.5 py-1 text-xs transition',
                filter === item.id ? 'bg-accent text-accent-fg font-medium' : 'bg-panel2 text-muted hover:text-fg'
              )}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}

      {q.isLoading ? <Loading /> : q.error ? <ErrorNote error={q.error} /> : items.length === 0 ? (
        <Card><EmptyState icon={Bell} title={t('Chưa có thông báo')} /></Card>
      ) : filtered.length === 0 ? (
        <Card><p className="py-8 text-center text-sm text-muted">{t('Không có thông báo nào phù hợp với bộ lọc.')}</p></Card>
      ) : (
        <div className="space-y-2">
          {filtered.map((n) => (
            <Card key={n.id} className={cn('p-4', !n.read && 'border-accent/50')}>
              <div className="flex items-start gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2"><span className="font-medium">{n.title}</span><Badge>{n.source}</Badge>{!n.read && <Badge tone="accent">{t('Mới')}</Badge>}<span className="text-xs text-muted">{timeAgo(n.ts)}</span></div>
                  <p className="mt-1 whitespace-pre-wrap break-words text-sm text-muted">{n.body}</p>
                  {n.session_id && <Link to={`/chat?session=${n.session_id}`} className="mt-1.5 inline-block text-xs text-accent hover:underline">{t('Xem hội thoại')}</Link>}
                </div>
                {!n.read && <Button size="sm" variant="ghost" onClick={() => readOne.mutate(n.id)}>{t('Đã đọc')}</Button>}
              </div>
            </Card>
          ))}
        </div>
      )}
    </Page>
  )
}
