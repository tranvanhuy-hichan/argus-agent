export interface ProviderCfg {
  cli?: 'claude' | 'agy' | 'codex' | 'custom'
  command?: string
  vision?: boolean
  price_in?: number
  price_out?: number
  type: 'openai' | 'anthropic' | 'cli'
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
  oauth?: boolean; oauth_scope?: string; service?: boolean
  enabled: boolean; confirm: boolean
}
export interface CatalogService {
  id: string; name: string; url: string; group: string; auth: 'oauth' | 'open' | 'token'; transport: 'http' | 'sse'; color: string
  desc: { vi: string; en: string }
  token?: { header: string; prefix: string; help_url: string; hint: { vi: string; en: string } }
}
export interface Catalog { groups: { id: string; label: { vi: string; en: string } }[]; services: CatalogService[] }
export interface RegistryItem { id: string; name: string; description: string; website: string; url: string; transport: 'http' | 'sse'; publisher: string; community: boolean; needs_header: string[] }
export interface McpTool { name: string; full_name: string; description: string; read_only: boolean }
export interface McpServerInfo { name: string; config: McpServerCfg; status: 'connecting' | 'connected' | 'error' | 'disabled' | 'needs_auth'; error: string; tools: McpTool[]; oauth?: boolean; logged_in?: boolean; auth_url?: string }
export interface ApiToken { id: string; name: string; prefix: string; allow_exec: boolean; created: number; last_used: number | null }
export interface SkillEntry { enabled: boolean; api_key: string; env: Record<string, string> }
export interface AppConfig {
  default_provider: string
  fallback: string[]
  providers: Record<string, ProviderCfg>
  agent: { workspace: string; max_steps: number; max_history: number; confirm_exec: boolean; tools_enabled: Record<string, boolean>; compact_chars: number; exec_sandbox: 'none' | 'docker'; sandbox_image: string; sandbox_network: boolean; suggest_habits: boolean }
  heartbeat: { enabled: boolean; interval_minutes: number; provider: string | null }
  auth: { has_password: boolean }
  skills: Record<string, SkillEntry>
  mcp_servers: Record<string, McpServerCfg>
  clawhub_url: string
  browser: { enabled: boolean; headless: boolean; executable: string; allow_private: boolean; idle_minutes: number }
  memory: { embeddings: 'off' | 'auto' | 'ollama' | 'openai' | 'hash'; provider: string | null; model: string; auto_index: boolean }
  media: { image_provider: string | null; image_model: string; vision_provider: string | null }
  computer: { enabled: boolean }
  agents: { max_depth: number; max_parallel: number; task_max_steps: number; profiles: Record<string, AgentProfile> }
}
export interface AgentProfile { description: string; prompt: string; tools: string[]; provider: string | null; max_steps: number }
export interface MemoryStatus {
  embedding: { mode: string; backend: string | null; model_id: string | null; dim: number; reachable: boolean; error: string }
  vectors: { total: number; by_model: Record<string, number>; by_kind: Record<string, number> }
  notes: number; messages: number; fts: boolean
  reindex: { running: boolean; done: number; total: number; error: string; finished: number }
}
export interface Curation { old: string; new: string; removed: string[]; added: string[]; ok: boolean; reason: string }
export type ExtraCfg = Pick<AppConfig, 'browser' | 'memory' | 'media' | 'computer' | 'agents'>
export interface ToolInfo { name: string; description: string; risk: 'safe' | 'file' | 'exec' | 'network' | 'mcp' }
export interface SecretsStatus { enabled: boolean; source: 'env' | 'keychain' | 'file' | 'none'; encrypted: number; plaintext: number; failed: string[] }
export interface ConfigResponse { config: AppConfig; tools: ToolInfo[]; secrets?: SecretsStatus }

export interface SessionInfo { id: string; title: string; updated: number; created: number; source: string; turns: number; project?: string }
export interface ToolCall { id: string; name: string; args: Record<string, unknown> }
export interface WireMessage { role: 'user' | 'assistant' | 'tool'; content: string; tool_calls?: ToolCall[]; tool_call_id?: string; attachments?: string[] }
export interface FileEntry { path: string; dir: boolean; size: number; mtime: number }

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

export interface PlanItem { id: number; text: string; status: 'pending' | 'in_progress' | 'done' | 'blocked'; note: string }
export interface Task {
  id: string; kind: 'task' | 'subagent'; title: string; goal: string; role: string; status: 'queued' | 'running' | 'done' | 'failed' | 'cancelled' | 'interrupted'
  steps: number; max_steps: number; progress: string; result: string; error: string; session_id: string | null
  created: number; started: number | null; finished: number | null; cancel_requested: boolean
}
export interface Job {
  id: string; name: string; schedule: string; prompt: string; provider: string | null; enabled: boolean
  last_run: number | null; last_status: 'ok' | 'error' | null; last_output: string | null; next_run: number | null; notify: boolean
}
export interface AuditItem { id: number; ts: number; session_id: string | null; source: string; tool: string; args: string; decision: string; ok: boolean; duration_ms: number; result: string }
export interface NotificationItem { id: number; ts: number; title: string; body: string; source: string; session_id: string | null; read: boolean }
export interface TelegramStatus { running: boolean; error: string; bot: string; enabled: boolean; has_token: boolean; allowed_users: number[]; api_base: string }
export interface HeartbeatStatus { enabled: boolean; interval_minutes: number; running: boolean; last_run: number | null; last_status: 'ok' | 'alert' | 'error' | null; last_output: string | null; next_run: number | null }
export interface SkillUpdate { name: string; current: string | null; latest: string }

export interface Dashboard {
  days: number
  totals: { llm_calls: number; prompt_tokens: number; completion_tokens: number; avg_latency_ms: number; llm_errors: number; tool_calls: number; tool_errors: number; sessions: number; messages: number; cost: number }
  series: { date: string; calls: number; prompt: number; completion: number; tools: number }[]
  by_provider: { provider: string; model: string; calls: number; tokens: number; latency: number; errors: number; cost: number }[]
  top_tools: { name: string; n: number; errors: number; avg_ms: number }[]
  skills: { total: number; active: number; needs_setup: number }
  automations: { total: number; enabled: number; next: number | null }
  providers: { default: string; count: number }
  recent_sessions: SessionInfo[]
}

export interface HabitDraft { kind: 'skill' | 'automation'; name: string; title: string; description: string; body: string; prompt: string; schedule: string }
export interface HabitSuggestion { id: string; status: string; count: number; examples: string[]; draft: HabitDraft | null; created: number }

export interface GitFile { path: string; status: 'new' | 'modified' | 'deleted' }
export interface GitStatus { repo: boolean; branch: string; files: GitFile[] }
export interface BrowseResult { path: string; parent: string | null; git: boolean; dirs: { name: string; path: string; git: boolean }[] }
export interface RecentProject { path: string; name: string; ts: number; git?: boolean; branch?: string }
