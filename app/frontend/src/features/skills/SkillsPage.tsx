import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Compass, PackagePlus, Plus, Puzzle, Search, Settings2 } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Form'
import { EmptyState, ErrorNote, Loading, Page, PageHeader } from '@/components/ui/misc'
import { Switch } from '@/components/ui/Switch'
import { Tabs } from '@/components/ui/Tabs'
import { useToast } from '@/components/ui/Toast'
import { useConfig, useSaveConfig, useSkills, useSkillUpdates } from '@/lib/queries'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { Skill } from '@/lib/types'
import { errMsg } from '@/lib/utils'
import { CreateSkillModal } from './CreateSkillModal'
import { Discover } from './Discover'
import { SkillModal } from './SkillModal'
import { t } from '@/lib/i18n.ts'

export function missingText(m: string): string {
  const [kind, ...rest] = m.split(':')
  const v = rest.join(':')
  return ({ bin: t('Thiếu lệnh: {v}', { v }), anyBin: t('Cần một trong: {v}', { v: v.replace(/\|/g, ', ') }), env: t('Thiếu biến môi trường: {v}', { v }), os: t('Chỉ hỗ trợ: {v}', { v }), config: t('Cần cấu hình riêng: {v}', { v }) } as Record<string, string>)[kind] ?? m
}

export function SkillIcon({ emoji }: { emoji?: string }) {
  return <div className="grid size-10 shrink-0 place-items-center rounded-xl bg-panel2 text-xl">{emoji || <Puzzle className="size-5 text-muted" />}</div>
}

export function SkillsPage() {
  const skills = useSkills()
  const cfg = useConfig()
  const save = useSaveConfig()
  const updates = useSkillUpdates()
  const qc = useQueryClient()
  const update = useMutation({
    mutationFn: (name: string) => api.post(`/api/skills/${name}/update`),
    onSuccess: () => { toast(t('Đã cập nhật skill')); void qc.invalidateQueries({ queryKey: ['skills'] }); void qc.invalidateQueries({ queryKey: ['skill-updates'] }) },
    onError: (e) => toast(errMsg(e), 'bad'),
  })
  const toast = useToast()
  const [params, setParams] = useSearchParams()
  const tab = params.get('tab') === 'discover' ? 'discover' : 'installed'
  const setTab = (t: 'installed' | 'discover') => setParams(t === 'discover' ? { tab: t } : {}, { replace: true })
  const [filter, setFilter] = useState('')
  const [selected, setSelected] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  const toggle = (s: Skill, enabled: boolean) => {
    if (!cfg.data) return
    const c = structuredClone(cfg.data.config)
    c.skills[s.name] = { ...(c.skills[s.name] ?? { api_key: '', env: {} }), enabled }
    save.mutate(c, { onError: (e) => toast(errMsg(e), 'bad') })
  }

  const list = (skills.data ?? []).filter((s) => !filter || `${s.name} ${s.description}`.toLowerCase().includes(filter.toLowerCase()))

  return (
    <Page>
      <PageHeader
        title={t('Kỹ năng')}
        action={<Button variant="primary" onClick={() => setCreating(true)}><Plus className="size-4" />{t('Tạo skill')}</Button>}
      />
      <Tabs
        value={tab}
        onChange={setTab}
        tabs={[{ id: 'installed', label: t('Đã cài'), count: skills.data?.length }, { id: 'discover', label: t('Khám phá ClawHub') }]}
      />
      <div className="mt-5">
        {tab === 'discover' ? (
          <Discover installed={skills.data ?? []} />
        ) : skills.isLoading ? (
          <Loading />
        ) : skills.error ? (
          <ErrorNote error={skills.error} />
        ) : (
          <>
            <div className="relative mb-4 max-w-sm">
              <Search className="pointer-events-none absolute left-3 top-2.5 size-4 text-muted" />
              <Input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder={t('Lọc skill đã cài…')} className="pl-9" aria-label={t('Lọc skill')} />
            </div>
            {list.length === 0 ? (
              <EmptyState icon={PackagePlus} title={t('Chưa có skill nào')} action={<Button onClick={() => setTab('discover')}><Compass className="size-4" />{t('Khám phá ClawHub')}</Button>} />
            ) : (
              <div className="overflow-hidden rounded-xl border border-line bg-panel">
                {list.map((s) => (
                  <div key={s.name} className="flex items-center gap-4 border-b border-line px-4 py-3.5 last:border-b-0">
                    <SkillIcon emoji={s.emoji} />
                    <button onClick={() => setSelected(s.name)} className="min-w-0 flex-1 text-left">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium">{s.name}</span>
                        {s.origin && <Badge tone="info">ClawHub · {s.origin.owner}{s.origin.version ? ` v${s.origin.version}` : ''}</Badge>}
                        {!s.eligible && <Badge tone="warn">{t('Cần thiết lập')}</Badge>}
                        {!s.enabled && <Badge>{t('Tạm tắt')}</Badge>}
                      </div>
                      <p className="mt-0.5 line-clamp-2 text-[13px] text-muted">{s.description || t('Không có mô tả')}</p>
                      {!s.eligible && <p className="mt-1 text-xs text-warn">{s.missing.map(missingText).join(' · ')}</p>}
                    </button>
                    {updates.data?.find((u) => u.name === s.name) && (
                      <Button size="sm" variant="primary" loading={update.isPending && update.variables === s.name} onClick={() => update.mutate(s.name)}>{t('Cập nhật v{v}', { v: updates.data.find((u) => u.name === s.name)?.latest ?? '' })}</Button>
                    )}
                    <Button variant="ghost" size="sm" onClick={() => setSelected(s.name)} aria-label={t('Cấu hình {name}', { name: s.name })}><Settings2 className="size-4" /></Button>
                    <Switch checked={s.enabled} onChange={(v) => toggle(s, v)} label={t('Bật {name}', { name: s.name })} />
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
      <SkillModal name={selected} onClose={() => setSelected(null)} />
      <CreateSkillModal open={creating} onClose={() => setCreating(false)} />
    </Page>
  )
}
