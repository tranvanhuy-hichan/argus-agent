import { useSearchParams } from 'react-router-dom'
import { Page, PageHeader } from '@/components/ui/misc'
import { Tabs } from '@/components/ui/Tabs'
import { ApiTab } from './ApiTab'
import { McpTab } from './McpTab'

export function IntegrationsPage() {
  const [params, setParams] = useSearchParams()
  const tab = params.get('tab') === 'api' ? 'api' : 'mcp'
  return (
    <Page>
      <PageHeader title="Tích hợp" subtitle="Nối agent với tool bên ngoài (MCP) và cho ứng dụng khác gọi agent." />
      <Tabs value={tab} onChange={(t) => setParams(t === 'api' ? { tab: t } : {}, { replace: true })} tabs={[{ id: 'mcp', label: 'MCP Servers' }, { id: 'api', label: 'API & Token' }]} />
      <div className="mt-5">{tab === 'api' ? <ApiTab /> : <McpTab />}</div>
    </Page>
  )
}
