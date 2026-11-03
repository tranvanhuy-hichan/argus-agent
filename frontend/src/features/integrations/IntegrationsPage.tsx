import { useSearchParams } from 'react-router-dom'
import { Page, PageHeader } from '@/components/ui/misc'
import { Tabs } from '@/components/ui/Tabs'
import { ApiTab } from './ApiTab'
import { ChannelsTab } from './ChannelsTab'
import { McpTab } from './McpTab'
import { t } from '@/lib/i18n.ts'

export function IntegrationsPage() {
  const [params, setParams] = useSearchParams()
  const tp = params.get('tab')
  const tab = tp === 'api' ? 'api' : tp === 'channels' ? 'channels' : 'mcp'
  return (
    <Page>
      <PageHeader title={t('Tích hợp')} subtitle={t('Nối agent với tool bên ngoài (MCP), kênh chat và cho ứng dụng khác gọi agent.')} />
      <Tabs value={tab} onChange={(v) => setParams(v === 'mcp' ? {} : { tab: v }, { replace: true })} tabs={[{ id: 'mcp', label: t('Máy chủ MCP') }, { id: 'channels', label: t('Kênh chat') }, { id: 'api', label: t('API & Token') }]} />
      <div className="mt-5">{tab === 'api' ? <ApiTab /> : tab === 'channels' ? <ChannelsTab /> : <McpTab />}</div>
    </Page>
  )
}
