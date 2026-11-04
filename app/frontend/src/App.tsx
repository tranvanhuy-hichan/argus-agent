import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from '@/components/layout/AppLayout'
import { NotificationsPage } from '@/features/notifications/NotificationsPage'
import { TasksPage } from './features/tasks/TasksPage'
import { AutomationsPage } from '@/features/automations/AutomationsPage'
import { CodePage } from '@/features/code/CodePage'
import { ChatPage } from '@/features/chat/ChatPage'
import { HomePage } from '@/features/home/HomePage'
import { IntegrationsPage } from '@/features/integrations/IntegrationsPage'
import { DocumentsPage } from '@/features/documents/DocumentsPage'
import { PluginsPage } from '@/features/plugins/PluginsPage'
import { ProvidersPage } from '@/features/providers/ProvidersPage'
import { SettingsPage } from '@/features/settings/SettingsPage'
import { SkillsPage } from '@/features/skills/SkillsPage'
import { WorkspacePage } from '@/features/workspace/WorkspacePage'
import { ActivityPage } from '@/features/activity/ActivityPage'
import { CODE_MODE } from '@/lib/features'
import { useLang } from '@/lib/i18n.ts'

// trình soạn thảo kéo theo highlight.js nên chỉ tải khi mở một dự án
const CodeWorkspace = lazy(() => import('@/features/code/CodeWorkspace').then((m) => ({ default: m.CodeWorkspace })))

export default function App() {
  useLang() // doi ngon ngu => App render lai => toan bo cay route tao lai phan tu va cap nhat chu
  return (
    <Routes>
      {CODE_MODE && <Route path="code/:sid" element={<div className="h-full"><Suspense fallback={null}><CodeWorkspace /></Suspense></div>} />}
      {!CODE_MODE && <Route path="code/*" element={<Navigate to="/" replace />} />}
      <Route element={<AppLayout />}>
        <Route index element={<HomePage />} />
        {CODE_MODE && <Route path="code" element={<CodePage />} />}
        <Route path="chat" element={<ChatPage />} />
        <Route path="activity" element={<ActivityPage />} />
        <Route path="dashboard" element={<Navigate to="/activity" replace />} />
        <Route path="automations" element={<AutomationsPage />} />
        <Route path="skills" element={<SkillsPage />} />
        <Route path="plugins" element={<PluginsPage />} />
        <Route path="documents" element={<DocumentsPage />} />
        <Route path="providers" element={<ProvidersPage />} />
        <Route path="integrations" element={<IntegrationsPage />} />
        <Route path="audit" element={<Navigate to="/activity?tab=log" replace />} />
        <Route path="tasks" element={<TasksPage />} />
        <Route path="notifications" element={<NotificationsPage />} />
        <Route path="workspace" element={<WorkspacePage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  )
}
