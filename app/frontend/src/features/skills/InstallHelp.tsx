import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Check, Copy, ExternalLink, Wrench } from 'lucide-react'
import { api } from '@/lib/api'
import { t } from '@/lib/i18n.ts'
import type { SkillTools } from '@/lib/types'
import { cn } from '@/lib/utils'

const OSES = [['mac', 'macOS'], ['linux', 'Linux'], ['windows', 'Windows']] as const
const here = (): 'mac' | 'linux' | 'windows' => (/Mac/i.test(navigator.platform) ? 'mac' : /Win/i.test(navigator.platform) ? 'windows' : 'linux')

/** Lenh cai dat tu "bin:x" / "anyBin:a|b" cua skill con thieu. */
export const binsOf = (missing: string[]) => missing.flatMap((m) => (m.startsWith('bin:') ? [m.slice(4)] : m.startsWith('anyBin:') ? m.slice(7).split('|') : []))

function CopyCmd({ cmd }: { cmd: string }) {
  const [done, setDone] = useState(false)
  return (
    <button onClick={() => { void navigator.clipboard.writeText(cmd).then(() => { setDone(true); setTimeout(() => setDone(false), 1500) }) }} title={t('Sao chép')} aria-label={t('Sao chép')}
      className="group flex min-w-0 flex-1 items-center gap-2 rounded-md bg-bg px-2 py-1 text-left font-mono text-[12px] hover:bg-panel2">
      <span className="min-w-0 flex-1 truncate">{cmd}</span>
      {done ? <Check className="size-3.5 shrink-0 text-ok" /> : <Copy className="size-3.5 shrink-0 text-muted group-hover:text-fg" />}
    </button>
  )
}

/** Huong dan cai cong cu dong lenh (macOS / Linux / Windows) cho cac skill can chuong trinh ngoai. */
export function InstallHelp({ bins, defaultOpen = false }: { bins: string[]; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen)
  const q = useQuery({ queryKey: ['skill-tools'], queryFn: () => api.get<SkillTools>('/api/clawhub/tools'), staleTime: Infinity, enabled: open || bins.length > 0 })
  const known = bins.filter((b) => q.data?.[b])
  if (!known.length) return null
  const me = here()
  return (
    <div className="mt-1.5">
      <button onClick={() => setOpen(!open)} aria-expanded={open} className="flex items-center gap-1 text-xs text-accent hover:underline"><Wrench className="size-3" />{open ? t('Ẩn hướng dẫn cài') : t('Cách cài công cụ này')}</button>
      {open && (
        <div className="mt-2 space-y-3 rounded-lg border border-line bg-panel2 p-3">
          {known.map((b) => {
            const tool = q.data![b]
            return (
              <div key={b}>
                <div className="mb-1.5 flex items-center gap-2 text-xs font-semibold">{b}<a href={tool.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 font-normal text-muted hover:text-fg"><ExternalLink className="size-3" />{t('Trang chủ')}</a></div>
                <div className="space-y-1">
                  {OSES.map(([id, label]) => (
                    <div key={id} className="flex items-center gap-2 text-xs">
                      <span className={cn('w-16 shrink-0', id === me ? 'font-semibold text-fg' : 'text-muted')}>{label}</span>
                      {tool[id] ? <CopyCmd cmd={tool[id]!} /> : <span className="text-muted">{id === 'windows' || id === 'linux' ? t('Xem hướng dẫn ở trang chủ') : t('Không hỗ trợ')}</span>}
                    </div>
                  ))}
                </div>
              </div>
            )
          })}
          <p className="text-[11px] text-muted">{t('Chạy lệnh trong Terminal (PowerShell trên Windows), rồi khởi động lại Argus để nhận lệnh mới.')}</p>
        </div>
      )}
    </div>
  )
}
