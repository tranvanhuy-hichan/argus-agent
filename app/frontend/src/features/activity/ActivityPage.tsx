import { lazy, Suspense } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Loading } from '@/components/ui/misc'
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
    <div className="flex h-full flex-col">
      <div className="shrink-0 px-4 pt-4 sm:px-8 lg:px-10">
        <Tabs value={tab} onChange={(v) => setParams(v === 'stats' ? {} : { tab: v }, { replace: true })}
          tabs={[{ id: 'stats', label: t('Thống kê & chi phí') }, { id: 'log', label: t('Lịch sử thao tác') }]} />
      </div>
      <div className="min-h-0 flex-1">
        {tab === 'stats' ? <Suspense fallback={<Loading />}><DashboardPage /></Suspense> : <AuditPage />}
      </div>
    </div>
  )
}
