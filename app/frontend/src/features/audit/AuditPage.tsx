import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronRight } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Select } from '@/components/ui/Form'
import { EmptyState, ErrorNote, Loading, Page, PageHeader } from '@/components/ui/misc'
import { api } from '@/lib/api'
import type { AuditItem } from '@/lib/types'
import { cn, fmtDateTime } from '@/lib/utils'
import { ScrollText } from 'lucide-react'
import { t, tk } from '@/lib/i18n.ts'

const PAGE = 50
const DEC: Record<string, { label: string; tone: 'ok' | 'bad' | 'warn' | 'neutral' }> = { approved: { label: tk('Cho phép'), tone: 'ok' }, denied: { label: tk('Từ chối'), tone: 'bad' }, auto: { label: tk('Tự động'), tone: 'neutral' }, full_access: { label: tk('Toàn quyền (không hỏi)'), tone: 'warn' } }

export function AuditPage() {
  const [tool, setTool] = useState('')
  const [decision, setDecision] = useState('')
  const [source, setSource] = useState('')
  const [page, setPage] = useState(0)
  const [open, setOpen] = useState<number | null>(null)
  const q = useQuery({
    queryKey: ['audit', tool, decision, source, page],
    queryFn: () => api.get<{ total: number; items: AuditItem[] }>(`/api/audit?limit=${PAGE}&offset=${page * PAGE}&tool=${tool}&decision=${decision}&source=${source}`),
    refetchInterval: 10_000,
  })
  const reset = (fn: () => void) => { fn(); setPage(0) }

  return (
    <Page>
      <PageHeader title={t('Nhật ký hoạt động')} />
      <div className="mb-4 flex flex-wrap gap-3">
        <Select value={decision} onChange={(e) => reset(() => setDecision(e.target.value))} className="w-44" aria-label={t('Quyết định')}><option value="">{t('Mọi quyết định')}</option><option value="approved">{t('Cho phép')}</option><option value="denied">{t('Từ chối')}</option><option value="auto">{t('Tự động')}</option><option value="full_access">{t('Toàn quyền (không hỏi)')}</option></Select>
        <Select value={source} onChange={(e) => reset(() => setSource(e.target.value))} className="w-44" aria-label={t('Nguồn')}><option value="">{t('Mọi nguồn')}</option><option value="chat">{t('Trò chuyện')}</option><option value="api">API</option><option value="telegram">Telegram</option><option value="cron">{t('Tự động hóa')}</option><option value="heartbeat">Heartbeat</option></Select>
        <Select value={tool} onChange={(e) => reset(() => setTool(e.target.value))} className="w-44" aria-label={t('Công cụ')}><option value="">{t('Mọi tool')}</option>{['exec', 'write', 'edit', 'read', 'web_fetch', 'web_search', 'http_request', 'memory_search', 'notify'].map((n) => <option key={n}>{n}</option>)}</Select>
      </div>
      {q.isLoading ? <Loading /> : q.error ? <ErrorNote error={q.error} /> : q.data?.items.length === 0 ? (
        <Card><EmptyState icon={ScrollText} title={t('Chưa có hoạt động nào')} /></Card>
      ) : (
        <>
          <Card className="overflow-hidden">
            {q.data?.items.map((i) => (
              <div key={i.id} className="border-b border-line last:border-b-0">
                <button onClick={() => setOpen(open === i.id ? null : i.id)} aria-expanded={open === i.id} className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm hover:bg-panel2">
                  <ChevronRight className={cn('size-3.5 shrink-0 text-muted transition', open === i.id && 'rotate-90')} />
                  <span className="w-28 shrink-0 text-xs tabular-nums text-muted">{fmtDateTime(i.ts)}</span>
                  <span className="w-28 shrink-0 font-mono text-[13px] font-medium">{i.tool}</span>
                  <span className="min-w-0 flex-1 truncate font-mono text-xs text-muted">{i.args}</span>
                  <Badge tone={DEC[i.decision]?.tone ?? 'neutral'}>{DEC[i.decision] ? t(DEC[i.decision].label) : i.decision}</Badge>
                  <Badge tone={i.ok ? 'ok' : 'bad'}>{i.ok ? 'OK' : t('Lỗi')}</Badge>
                  <Badge>{i.source}</Badge>
                  <span className="hidden w-14 shrink-0 text-right text-xs tabular-nums text-muted sm:block">{i.duration_ms}ms</span>
                </button>
                {open === i.id && (
                  <div className="space-y-2 border-t border-line bg-bg px-5 py-3">
                    <pre className="whitespace-pre-wrap break-all font-mono text-xs text-muted">{i.args}</pre>
                    <pre className="max-h-60 overflow-auto whitespace-pre-wrap font-mono text-xs">{i.result || t('(trống)')}</pre>
                  </div>
                )}
              </div>
            ))}
          </Card>
          <div className="mt-4 flex items-center justify-between text-sm text-muted">
            <span>{t('{n} mục', { n: q.data?.total ?? 0 })}</span>
            <div className="flex items-center gap-2"><Button size="sm" disabled={page === 0} onClick={() => setPage(page - 1)}>{t('Trước')}</Button><span>{t('Trang {n}', { n: page + 1 })}</span><Button size="sm" disabled={(page + 1) * PAGE >= (q.data?.total ?? 0)} onClick={() => setPage(page + 1)}>{t('Sau')}</Button></div>
          </div>
        </>
      )}
    </Page>
  )
}
