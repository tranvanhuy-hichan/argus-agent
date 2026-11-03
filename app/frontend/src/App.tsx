import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import { AppLayout } from '@/components/layout/AppLayout'
import { AuditPage } from '@/features/audit/AuditPage'
import { NotificationsPage } from '@/features/notifications/NotificationsPage'
import { AutomationsPage } from '@/features/automations/AutomationsPage'
import { ChatPage } from '@/features/chat/ChatPage'
import { HomePage } from '@/features/home/HomePage'
import { IntegrationsPage } from '@/features/integrations/IntegrationsPage'
import { ProvidersPage } from '@/features/providers/ProvidersPage'
import { SettingsPage } from '@/features/settings/SettingsPage'
import { SkillsPage } from '@/features/skills/SkillsPage'
import { WorkspacePage } from '@/features/workspace/WorkspacePage'
import { Loading } from '@/components/ui/misc'
import { useLang } from '@/lib/i18n.ts'

// recharts nang nen chi tai khi mo Dashboard
const DashboardPage = lazy(() => import('@/features/dashboard/DashboardPage').then((m) => ({ default: m.DashboardPage })))

export default function App() {
  useLang() // doi ngon ngu => App render lai => toan bo cay route tao lai phan tu va cap nhat chu
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<HomePage />} />
        <Route path="chat" element={<ChatPage />} />
        <Route path="dashboard" element={<Suspense fallback={<Loading />}><DashboardPage /></Suspense>} />
        <Route path="automations" element={<AutomationsPage />} />
        <Route path="skills" element={<SkillsPage />} />
        <Route path="providers" element={<ProvidersPage />} />
        <Route path="integrations" element={<IntegrationsPage />} />
        <Route path="audit" element={<AuditPage />} />
        <Route path="notifications" element={<NotificationsPage />} />
        <Route path="workspace" element={<WorkspacePage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  )
}
