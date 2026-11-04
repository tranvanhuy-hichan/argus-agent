import { useEffect, useState } from 'react'
import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { BadgeCheck, Download, Search } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Select } from '@/components/ui/Form'
import { EmptyState, ErrorNote, Loading } from '@/components/ui/misc'
import { api } from '@/lib/api'
import type { HubSkill, Skill } from '@/lib/types'
import { fmtNum, timeAgo } from '@/lib/utils'
import { HubSkillModal } from './HubSkillModal'
import { SkillIcon } from './SkillsPage'
import { t, tk } from '@/lib/i18n.ts'

const SORTS = [['downloads', tk('Tải nhiều nhất')], ['trending', tk('Xu hướng')], ['stars', tk('Đánh giá cao')], ['newest', tk('Mới nhất')], ['updated', tk('Cập nhật gần đây')]]

export const isInstalled = (installed: Skill[], s: HubSkill) => installed.some((i) => i.origin?.slug === s.slug && i.origin.owner === s.owner)

export function Discover({ installed, input }: { installed: Skill[]; input: string }) {
  const [q, setQ] = useState('')
  const [sort, setSort] = useState('downloads')
  const [picked, setPicked] = useState<HubSkill | null>(null)

  useEffect(() => {
    const t = setTimeout(() => setQ(input.trim()), 350)
    return () => clearTimeout(t)
  }, [input])

  const search = useQuery({ queryKey: ['hub-search', q], queryFn: () => api.get<HubSkill[]>(`/api/clawhub/search?q=${encodeURIComponent(q)}`), enabled: q.length > 1 })
  const browse = useInfiniteQuery({
    queryKey: ['hub-browse', sort],
    queryFn: ({ pageParam }) => api.get<{ items: HubSkill[]; next: string | null }>(`/api/clawhub/browse?sort=${sort}${pageParam ? `&cursor=${encodeURIComponent(pageParam)}` : ''}`),
    initialPageParam: '',
    getNextPageParam: (last) => last.next ?? undefined,
    enabled: q.length <= 1,
  })

  const searching = q.length > 1
  const items = searching ? search.data : browse.data?.pages.flatMap((p) => p.items)
  const state = searching ? search : browse

  return (
    <div>
      <div className="mb-4 flex flex-wrap gap-3">
        {!searching && <Select value={sort} onChange={(e) => setSort(e.target.value)} className="w-48" aria-label={t('Sắp xếp')}>{SORTS.map(([v, l]) => <option key={v} value={v}>{t(l)}</option>)}</Select>}
      </div>
      <p className="mb-3 text-xs text-muted">{t('Nguồn: clawhub.ai · chỉ hiển thị skill chưa bị gắn cờ đáng ngờ. Hãy đọc kỹ SKILL.md trước khi cài, vì skill có thể yêu cầu agent chạy lệnh.')}</p>

      {state.isLoading ? <Loading /> : state.error ? <ErrorNote error={state.error} /> : !items?.length ? (
        <EmptyState icon={Search} title={t('Không tìm thấy skill nào')} />
      ) : (
        <>
          <div className="overflow-hidden rounded-xl border border-line bg-panel">
            {items.map((s) => (
              <button key={`${s.owner}/${s.slug}`} onClick={() => setPicked(s)} className="flex w-full items-center gap-4 border-b border-line px-4 py-3.5 text-left transition last:border-b-0 hover:bg-panel2">
                <SkillIcon />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{s.name}</span>
                    <span className="text-xs text-muted">@{s.owner}</span>
                    {s.official && <Badge tone="accent"><BadgeCheck className="size-3" />{t('Chính thức')}</Badge>}
                    {isInstalled(installed, s) && <Badge tone="ok">{t('Đã cài')}</Badge>}
                  </div>
                  <p className="mt-0.5 line-clamp-2 text-[13px] text-muted">{s.summary}</p>
                </div>
                <div className="hidden shrink-0 text-right text-xs text-muted sm:block">
                  <p className="flex items-center justify-end gap-1"><Download className="size-3" />{fmtNum(s.downloads)}</p>
                  <p>{timeAgo(s.updated)}</p>
                </div>
              </button>
            ))}
          </div>
          {!searching && browse.hasNextPage && (
            <div className="mt-4 flex justify-center"><Button loading={browse.isFetchingNextPage} onClick={() => void browse.fetchNextPage()}>{t('Tải thêm')}</Button></div>
          )}
        </>
      )}
      <HubSkillModal skill={picked} installed={picked ? isInstalled(installed, picked) : false} onClose={() => setPicked(null)} />
    </div>
  )
}
