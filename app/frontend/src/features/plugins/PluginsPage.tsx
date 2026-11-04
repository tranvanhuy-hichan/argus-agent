import { useState } from 'react'
import { Page, PageHeader } from '@/components/ui/misc'
import { SearchBox } from '@/components/ui/SearchBox'
import { t } from '@/lib/i18n.ts'
import { ServicesTab } from '@/features/integrations/ServicesTab'

/** Plugin: các dịch vụ bên ngoài (GitHub, Notion, Canva…) bật bằng một cú bấm, dựa trên MCP từ xa. */
export function PluginsPage() {
  const [q, setQ] = useState('')
  return (
    <Page>
      <PageHeader title={t('Plugin')} action={<SearchBox value={q} onChange={setQ} placeholder={t('Tìm plugin (ví dụ vercel, github, stripe…)')} label={t('Tìm plugin')} />} />
      <ServicesTab q={q} />
    </Page>
  )
}
