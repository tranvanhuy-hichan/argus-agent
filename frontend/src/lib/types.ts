export interface ProviderCfg {
  type: 'openai' | 'anthropic'
  base_url: string
  model: string
  api_key: string
  api_key_env: string
  temperature: number
}
export interface McpServerCfg {
  transport: 'stdio' | 'http' | 'sse'
  command: string; args: string[]; env: Record<string, string>; cwd: string
  url: string; headers: Record<string, string>
  enabled: boolean; confirm: boolean
}
export interface McpTool { name: string; full_name: string; description: string; read_only: boolean }
export interface McpServerInfo { name: string; config: McpServerCfg; status: 'connecting' | 'connected' | 'error' | 'disabled'; error: string; tools: McpTool[] }
export interface ApiToken { id: string; name: string; prefix: string; allow_exec: boolean; created: number; last_used: number | null }
export interface SkillEntry { enabled: boolean; api_key: string; env: Record<string, string> }
export interface AppConfig {
  default_provider: string
  fallback: string[]
  providers: Record<string, ProviderCfg>
  agent: { workspace: string; max_steps: number; max_history: number; confirm_exec: boolean; tools_enabled: Record<string, boolean> }
  skills: Record<string, SkillEntry>
  mcp_servers: Record<string, McpServerCfg>
  clawhub_url: string
}
export interface ToolInfo { name: string; description: string; risk: 'safe' | 'file' | 'exec' | 'network' | 'mcp' }
export interface ConfigResponse { config: AppConfig; tools: ToolInfo[] }

export interface SessionInfo { id: string; title: string; updated: number; created: number; source: string; turns: number }
export interface ToolCall { id: string; name: string; args: Record<string, unknown> }
export interface WireMessage { role: 'user' | 'assistant' | 'tool'; content: string; tool_calls?: ToolCall[]; tool_call_id?: string }

export interface Skill {
  name: string; description: string; path: string; enabled: boolean; eligible: boolean; missing: string[]
  emoji: string; homepage: string; primary_env: string; model_invocable: boolean
  origin: { source: string; slug: string; owner: string; version: string | null; installedAt: number } | null
  requires: { bins?: string[]; anyBins?: string[]; env?: string[]; config?: string[] }
}
export interface SkillDetail extends Skill { body: string; files: string[] }

export interface HubSkill {
  slug: string; owner: string; name: string; summary: string; downloads: number; stars: number
  version: string | null; updated: number | null; official: boolean; installable: boolean; topics: string[]
}
export interface HubDetail extends HubSkill {
  moderation: { isSuspicious?: boolean; isMalwareBlocked?: boolean; verdict?: string; summary?: string; reasonCodes?: string[] } | null
  changelog?: string | null; license?: string | null; skill_md: string | null
}

export interface Job {
  id: string; name: string; schedule: string; prompt: string; provider: string | null; enabled: boolean
  last_run: number | null; last_status: 'ok' | 'error' | null; last_output: string | null; next_run: number | null
}

export interface Dashboard {
  days: number
  totals: { llm_calls: number; prompt_tokens: number; completion_tokens: number; avg_latency_ms: number; llm_errors: number; tool_calls: number; tool_errors: number; sessions: number; messages: number }
  series: { date: string; calls: number; prompt: number; completion: number; tools: number }[]
  by_provider: { provider: string; model: string; calls: number; tokens: number; latency: number; errors: number }[]
  top_tools: { name: string; n: number; errors: number; avg_ms: number }[]
  skills: { total: number; active: number; needs_setup: number }
  automations: { total: number; enabled: number; next: number | null }
  providers: { default: string; count: number }
  recent_sessions: SessionInfo[]
}
