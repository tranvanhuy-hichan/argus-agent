import { useState } from 'react'
import { Navigate, useSearchParams } from 'react-router-dom'
import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Page, PageHeader } from '@/components/ui/misc'
import { Tabs } from '@/components/ui/Tabs'
import { ApiTab } from './ApiTab'
import { ChannelsTab } from './ChannelsTab'
import { McpTab } from './McpTab'
import { t } from '@/lib/i18n.ts'

export function IntegrationsPage() {
  const [params, setParams] = useSearchParams()
  const [add, setAdd] = useState(0)
  const tp = params.get('tab')
  if (tp === 'services') return <Navigate to="/plugins" replace /> // tab cũ đã chuyển thành mục Plugin riêng
  const tab = tp === 'api' ? 'api' : tp === 'channels' ? 'channels' : 'mcp'
  return (
    <Page>
      <PageHeader title={t('Tích hợp')} />
      <Tabs value={tab} onChange={(v) => { setAdd(0); setParams(v === 'mcp' ? {} : { tab: v }, { replace: true }) }} tabs={[{ id: 'mcp', label: t('MCP server') }, { id: 'channels', label: t('Kênh chat') }, { id: 'api', label: t('API & Token') }]}
        right={tab === 'mcp' || tab === 'api' ? <Button variant="primary" onClick={() => setAdd(add + 1)}><Plus className="size-4" />{tab === 'mcp' ? t('Thêm MCP server') : t('Tạo token')}</Button> : undefined} />
      <div className="mt-5">{tab === 'api' ? <ApiTab addSignal={add} /> : tab === 'channels' ? <ChannelsTab /> : <McpTab addSignal={add} />}</div>
    </Page>
  )
}
