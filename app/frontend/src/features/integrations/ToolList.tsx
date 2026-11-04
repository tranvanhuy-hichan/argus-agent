import { Badge } from '@/components/ui/Badge'
import { Switch } from '@/components/ui/Switch'
import type { McpTool } from '@/lib/types'
import { t } from '@/lib/i18n.ts'

/** Cac cong cu cua mot MCP server, moi cong cu co cong tac bat/tat (tat thi agent khong thay va khong goi duoc). */
export function ToolList({ tools, enabled, onToggle }: { tools: McpTool[]; enabled: Record<string, boolean>; onToggle: (name: string, on: boolean) => void }) {
  if (!tools.length) return null
  return (
    <div className="border-t border-line">
      {tools.map((tl) => (
        <div key={tl.full_name} className="flex items-center gap-4 border-b border-line px-5 py-2.5 last:border-b-0">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2"><span className="font-mono text-[13px]">{tl.full_name}</span>{tl.read_only && <Badge tone="ok">read-only</Badge>}</div>
            <p className="line-clamp-2 text-xs text-muted">{tl.description}</p>
          </div>
          <Switch checked={enabled[tl.full_name] !== false} onChange={(v) => onToggle(tl.full_name, v)} label={t('Bật tool {name}', { name: tl.full_name })} />
        </div>
      ))}
    </div>
  )
}
