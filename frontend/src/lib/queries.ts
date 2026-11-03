import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './api'
import type { ApiToken, AppConfig, ConfigResponse, Dashboard, Job, McpServerInfo, SessionInfo, Skill } from './types'

export const useConfig = () => useQuery({ queryKey: ['config'], queryFn: () => api.get<ConfigResponse>('/api/config') })
export const useSkills = () => useQuery({ queryKey: ['skills'], queryFn: () => api.get<Skill[]>('/api/skills') })
export const useSessions = () => useQuery({ queryKey: ['sessions'], queryFn: () => api.get<SessionInfo[]>('/api/sessions') })
export const useJobs = () => useQuery({ queryKey: ['jobs'], queryFn: () => api.get<Job[]>('/api/automations') })
export const useMcp = () => useQuery({
  queryKey: ['mcp'],
  queryFn: () => api.get<McpServerInfo[]>('/api/mcp'),
  refetchInterval: (q) => (q.state.data?.some((s) => s.status === 'connecting') ? 1500 : 10_000),
})
export const useTokens = () => useQuery({ queryKey: ['tokens'], queryFn: () => api.get<ApiToken[]>('/api/tokens') })
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
