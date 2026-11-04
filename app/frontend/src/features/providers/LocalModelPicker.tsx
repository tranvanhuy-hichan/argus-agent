import { useQuery } from '@tanstack/react-query'
import { Cpu, ExternalLink, RefreshCw, Terminal } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { api } from '@/lib/api'
import { t } from '@/lib/i18n.ts'
import { Choice, CopyButton } from './EmbeddingPanel'

interface Recommend {
  hardware: { ram_gb: number; gpu: string; vram_gb: number; cpus: number; os: string }
  ollama: { running: boolean; installed: boolean }
  installed_models: string[]
  models: { name: string; size_gb: number; desc: string; fit: 'gpu' | 'cpu' | 'heavy'; installed: boolean; recommended: boolean }[]
}

const INSTALL_CMD: Record<string, string> = { Linux: 'curl -fsSL https://ollama.com/install.sh | sh', Darwin: 'brew install ollama' }

/** Chọn model chạy trên máy: gợi ý theo phần cứng, hướng dẫn cài Ollama và tải model. */
export function LocalModelPicker({ baseUrl, model, onPick }: { baseUrl: string; model: string; onPick: (m: string) => void }) {
  const q = useQuery({ queryKey: ['ollama-recommend', baseUrl], queryFn: () => api.get<Recommend>(`/api/ollama/recommend?base_url=${encodeURIComponent(baseUrl)}`), staleTime: 10_000 })
  const d = q.data
  if (!d) return <p className="text-xs text-muted">{q.isError ? t('Không đọc được cấu hình máy.') : t('Đang đọc cấu hình máy…')}</p>
  const { hardware: hw, ollama } = d
  const cur = d.models.find((m) => m.name === model)
  const installCmd = INSTALL_CMD[hw.os]
  const fitBadge = (f: string) => f === 'gpu' ? <Badge tone="ok">{t('Chạy nhanh')}</Badge> : f === 'cpu' ? <Badge tone="warn">{t('Hơi chậm')}</Badge> : <Badge tone="bad">{t('Quá nặng')}</Badge>

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border border-line bg-panel2 px-3 py-2.5 text-xs">
        <Cpu className="size-4 shrink-0 text-accent" />
        <span className="font-medium">{t('Máy của bạn')}</span>
        <span className="text-muted">RAM {hw.ram_gb} GB</span>
        <span className="text-muted">{hw.gpu ? `${hw.gpu}${hw.vram_gb ? ` · ${hw.vram_gb} GB` : ''}` : t('Không có GPU rời, sẽ chạy bằng CPU')}</span>
        <span className="ml-auto flex items-center gap-2">
          {ollama.running ? <Badge tone="ok">{t('Ollama đang chạy')}</Badge> : <Badge tone="bad">{t('Chưa thấy Ollama')}</Badge>}
          <Button size="sm" variant="ghost" onClick={() => void q.refetch()} loading={q.isFetching} aria-label={t('Kiểm tra lại')}><RefreshCw className="size-3.5" /></Button>
        </span>
      </div>

      {!ollama.running && (
        <div className="space-y-2 rounded-lg border border-warn/40 bg-warn/10 p-3 text-xs">
          <p className="font-medium text-warn">{ollama.installed ? t('Đã cài Ollama nhưng chưa chạy. Mở ứng dụng Ollama, hoặc chạy lệnh dưới đây rồi bấm kiểm tra lại.') : t('Cần cài Ollama để chạy model trên máy.')}</p>
          <div className="flex flex-wrap items-center gap-3">
            {ollama.installed ? <><code className="rounded bg-bg px-2 py-1 font-mono text-[12px]">ollama serve</code><CopyButton text="ollama serve" /></>
              : installCmd ? <><code className="rounded bg-bg px-2 py-1 font-mono text-[12px]">{installCmd}</code><CopyButton text={installCmd} /></> : null}
            <a href="https://ollama.com/download" target="_blank" rel="noreferrer" className="ml-auto inline-flex items-center gap-1 text-accent hover:underline">{t('Tải Ollama')}<ExternalLink className="size-3" /></a>
          </div>
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2" role="radiogroup" aria-label={t('Model chạy trên máy')}>
        {d.models.map((m) => (
          <Choice key={m.name} on={model === m.name} onClick={() => onPick(m.name)} title={<span className="font-mono">{m.name}</span>}
            badge={<>{m.recommended && <Badge tone="accent">{t('Hợp với máy bạn')}</Badge>}{m.installed ? <Badge tone="ok">{t('Đã cài')}</Badge> : <Badge>{`~${m.size_gb} GB`}</Badge>}{fitBadge(m.fit)}</>}
            desc={t(m.desc)} />
        ))}
      </div>

      {ollama.running && model && !d.installed_models.includes(model) && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-line bg-panel2 px-3 py-2.5 text-xs">
          <Terminal className="size-4 shrink-0 text-accent" />
          <span className="text-muted">{t('Chưa tải model này. Mở terminal và chạy:')}</span>
          <code className="rounded bg-bg px-2 py-1 font-mono text-[12px]">ollama pull {model}</code>
          <CopyButton text={`ollama pull ${model}`} />
        </div>
      )}
      {cur?.fit === 'heavy' && <p className="text-xs text-bad">{t('Model này quá nặng so với máy bạn, có thể rất chậm hoặc tràn bộ nhớ.')}</p>}
    </div>
  )
}
