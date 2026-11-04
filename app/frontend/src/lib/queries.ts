import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './api'
import type { ApiToken, AppConfig, ConfigResponse, Dashboard, HeartbeatStatus, Job, McpServerInfo, HabitSuggestion, SessionInfo, Skill, SkillUpdate } from './types'

export const useConfig = () => useQuery({ queryKey: ['config'], queryFn: () => api.get<ConfigResponse>('/api/config') })
export const useSkills = () => useQuery({ queryKey: ['skills'], queryFn: () => api.get<Skill[]>('/api/skills') })
export const useSessions = () => useQuery({ queryKey: ['sessions'], queryFn: () => api.get<SessionInfo[]>('/api/sessions') })
export const useHabits = () => useQuery({ queryKey: ['habits'], queryFn: () => api.get<HabitSuggestion[]>('/api/habits'), refetchInterval: 30_000 })
export const useJobs = () => useQuery({ queryKey: ['jobs'], queryFn: () => api.get<Job[]>('/api/automations') })
export const useMcp = () => useQuery({
  queryKey: ['mcp'],
  queryFn: () => api.get<McpServerInfo[]>('/api/mcp'),
  refetchInterval: (q) => (q.state.data?.some((s) => s.status === 'connecting' || (s.status === 'needs_auth' && s.auth_url)) ? 1500 : 10_000),
})
export const useTokens = () => useQuery({ queryKey: ['tokens'], queryFn: () => api.get<ApiToken[]>('/api/tokens') })
export const useHeartbeat = () => useQuery({ queryKey: ['heartbeat'], queryFn: () => api.get<HeartbeatStatus>('/api/heartbeat'), refetchInterval: 10_000 })
export const useSkillUpdates = () => useQuery({ queryKey: ['skill-updates'], queryFn: () => api.get<SkillUpdate[]>('/api/skills/updates'), staleTime: 300_000 })
export const useDashboard = (days: number) => useQuery({ queryKey: ['dashboard', days], queryFn: () => api.get<Dashboard>(`/api/dashboard?days=${days}`), refetchInterval: 30_000 })

export function useSaveConfig() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (cfg: AppConfig) => api.put('/api/config', cfg),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['config'] })
      void qc.invalidateQueries({ queryKey: ['skills'] })
    },
  })
}
