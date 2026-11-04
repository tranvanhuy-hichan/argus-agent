import { lazy, Suspense } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Loading, Page, PageHeader } from '@/components/ui/misc'
import { Tabs } from '@/components/ui/Tabs'
import { AuditPage } from '@/features/audit/AuditPage'
import { t } from '@/lib/i18n.ts'

// recharts nang nen chi tai khi mo tab Thong ke
const DashboardPage = lazy(() => import('@/features/dashboard/DashboardPage').then((m) => ({ default: m.DashboardPage })))

/** Gop "Bang dieu khien" va "Nhat ky hoat dong": cung la cau hoi "agent da lam gi va ton bao nhieu". */
export function ActivityPage() {
  const [params, setParams] = useSearchParams()
  const tab = params.get('tab') === 'log' ? 'log' : 'stats'
  return (
    <Page>
      <PageHeader title={t('Thống kê')} />
      <Tabs value={tab} onChange={(v) => setParams(v === 'stats' ? {} : { tab: v }, { replace: true })}
        tabs={[{ id: 'stats', label: t('Thống kê & chi phí') }, { id: 'log', label: t('Lịch sử thao tác') }]} />
      <div className="mt-5">
        {tab === 'stats' ? <Suspense fallback={<Loading />}><DashboardPage /></Suspense> : <AuditPage />}
      </div>
    </Page>
  )
}
