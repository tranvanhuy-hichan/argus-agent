import type { Brand } from '@/components/ui/BrandIcon'
import type { McpServerCfg } from '@/lib/types'

/** Logo cua dich vu theo dia chi MCP (dung o danh sach may chu); null neu khong nhan ra. */
export function mcpBrand(cfg: Pick<McpServerCfg, 'url' | 'command' | 'args'>): Brand | null {
  const u = (cfg.url || '').toLowerCase()
  if (u.includes('notion.com')) return 'notion'
  if (u.includes('linear.app')) return 'linear'
  if (u.includes('canva.com')) return 'canva'
  if (u.includes('atlassian.com')) return 'atlassian'
  if (u.includes('asana.com')) return 'asana'
  if (/notion/.test(`${cfg.command} ${(cfg.args ?? []).join(' ')}`)) return 'notion'
  return null
}
