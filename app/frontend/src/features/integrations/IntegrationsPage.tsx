import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Page, PageHeader } from '@/components/ui/misc'
import { SearchBox } from '@/components/ui/SearchBox'
import { Tabs } from '@/components/ui/Tabs'
import { ApiTab } from './ApiTab'
import { ChannelsTab } from './ChannelsTab'
import { McpTab } from './McpTab'
import { ServicesTab } from './ServicesTab'
import { t } from '@/lib/i18n.ts'

export function IntegrationsPage() {
  const [params, setParams] = useSearchParams()
  const [add, setAdd] = useState(0)
  const [q, setQ] = useState('')
  const tp = params.get('tab')
  const tab = tp === 'api' ? 'api' : tp === 'channels' ? 'channels' : tp === 'services' ? 'services' : 'mcp'
  return (
    <Page>
      <PageHeader title={t('Tích hợp')} />
      <Tabs value={tab} onChange={(v) => { setAdd(0); setParams(v === 'mcp' ? {} : { tab: v }, { replace: true }) }} tabs={[{ id: 'mcp', label: t('MCP truyền thống') }, { id: 'services', label: t('MCP dịch vụ') }, { id: 'channels', label: t('Kênh chat') }, { id: 'api', label: t('API & Token') }]}
        right={tab === 'services' ? <SearchBox value={q} onChange={setQ} placeholder={t('Tìm dịch vụ (ví dụ vercel, github, stripe…)')} label={t('Tìm dịch vụ')} />
          : tab === 'mcp' || tab === 'api' ? <Button variant="primary" onClick={() => setAdd(add + 1)}><Plus className="size-4" />{tab === 'mcp' ? t('Thêm MCP server') : t('Tạo token')}</Button> : undefined} />
      <div className="mt-5">{tab === 'api' ? <ApiTab addSignal={add} /> : tab === 'channels' ? <ChannelsTab /> : tab === 'services' ? <ServicesTab q={q} /> : <McpTab addSignal={add} />}</div>
    </Page>
  )
}
