import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Check, Download } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { ErrorNote, Loading } from '@/components/ui/misc'
import { api } from '@/lib/api'
import { t, tk, useLang } from '@/lib/i18n.ts'
import type { HubSkill, Skill, SkillPick, SkillPicks } from '@/lib/types'
import { fmtNum } from '@/lib/utils'
import { HubSkillModal } from './HubSkillModal'
import { isInstalled } from './Discover'
import { InstallHelp } from './InstallHelp'
import { SkillIcon } from './SkillsPage'

const NEEDS = { key: tk('Cần khóa API hoặc tài khoản'), cli: tk('Cần cài thêm công cụ'), mac: tk('Chỉ macOS'), linux: tk('Chỉ Linux') } as const

const asHub = (p: SkillPick): HubSkill => ({ slug: p.slug, owner: p.owner, name: p.name, summary: '', downloads: p.downloads, stars: 0, version: p.version, updated: null, official: false, installable: p.installable, topics: [] })

/** Skill chon loc cho nguoi dung pho thong, nhom theo muc dich; bam vao de xem noi dung va cai. */
export function Picks({ installed }: { installed: Skill[] }) {
  const lang = useLang()
  const [picked, setPicked] = useState<SkillPick | null>(null)
  const q = useQuery({ queryKey: ['skill-picks'], queryFn: () => api.get<SkillPicks>('/api/clawhub/picks'), staleTime: 600_000 })
  if (q.isLoading) return <Loading />
  if (q.error || !q.data) return <ErrorNote error={q.error} />
  const { categories, items } = q.data
  return (
    <div className="space-y-7">
      <p className="text-xs text-muted">{t('Chọn lọc từ các skill được tải nhiều nhất trên ClawHub, hợp với công việc và đời sống hằng ngày. Bấm vào một skill để xem nội dung trước khi cài.')}</p>
      {categories.map((c) => {
        const list = items.filter((i) => i.category === c.id)
        if (!list.length) return null
        return (
          <section key={c.id}>
            <h3 className="mb-2.5 text-sm font-semibold">{lang === 'en' ? c.en : c.vi}</h3>
            <div className="grid gap-3 sm:grid-cols-2">
              {list.map((p) => {
                const done = isInstalled(installed, asHub(p))
                return (
                  <div key={`${p.owner}/${p.slug}`} className="flex gap-3 rounded-lg border border-line bg-panel p-3.5">
                    <SkillIcon />
                    <div className="min-w-0 flex-1"><button onClick={() => setPicked(p)} className="w-full text-left">
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-1"><span className="font-medium">{p.name}</span><span className="text-xs text-muted">@{p.owner}</span></div>
                      <p className="mt-0.5 text-[13px] text-muted">{lang === 'en' ? p.en : p.vi}</p>
                      <div className="mt-2 flex flex-wrap items-center gap-1.5">
                        {p.needs.map((n) => <Badge key={n} tone="warn">{t(NEEDS[n])}</Badge>)}
                        {p.downloads > 0 && <span className="flex items-center gap-1 text-[11px] text-muted"><Download className="size-3" />{fmtNum(p.downloads)}</span>}
                      </div>
                    </button>{p.bins.length > 0 && <InstallHelp bins={p.bins} />}</div>
                    {done ? <Badge tone="ok" className="self-start"><Check className="size-3" />{t('Đã cài')}</Badge> : <Button size="sm" className="self-start" onClick={() => setPicked(p)}>{t('Cài đặt')}</Button>}
                  </div>
                )
              })}
            </div>
          </section>
        )
      })}
      <HubSkillModal skill={picked ? asHub(picked) : null} installed={picked ? isInstalled(installed, asHub(picked)) : false} onClose={() => setPicked(null)} />
    </div>
  )
}
