import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Brain, Check, Cloud, Copy, ExternalLink, Laptop, Terminal } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { Field, Input, Select } from '@/components/ui/Form'
import { Switch } from '@/components/ui/Switch'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import type { AppConfig, MemoryStatus } from '@/lib/types'
import { errMsg } from '@/lib/utils'
import { t, tk } from '@/lib/i18n.ts'

function Row({ title, children }: { title: string; children: React.ReactNode }) {
  return <div className="-mx-5 flex items-center justify-between gap-4 border-b border-line/60 px-5 pb-4 last:border-b-0 last:pb-0 col-span-full"><p className="text-sm font-medium">{title}</p>{children}</div>
}

function MemoryStatusLine({ isDirty }: { isDirty?: boolean }) {
  const qc = useQueryClient()
  const toast = useToast()
  const q = useQuery({ queryKey: ['memory-status'], queryFn: () => api.get<MemoryStatus>('/api/memory/status'), refetchInterval: (s) => (s.state.data?.reindex.running ? 1500 : false) })
  const re = useMutation({ mutationFn: () => api.post('/api/memory/reindex', {}), onSuccess: () => void qc.invalidateQueries({ queryKey: ['memory-status'] }), onError: (e) => toast(errMsg(e), 'bad') })
  const d = q.data
  if (!d) return null
  const e = d.embedding
  return (
    <div className="space-y-2 rounded-lg border border-line bg-panel2 p-3 text-xs col-span-full">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-muted">{t('Đang áp dụng trong hệ thống:')}</span><span className="font-mono font-medium">{e.model_id ?? t('tắt')}</span>
        {e.backend && (e.reachable ? <Badge tone="ok">{t('kết nối được')}</Badge> : <Badge tone="bad">{t('không kết nối được')}</Badge>)}
        <span className="text-muted">{t('{n} đoạn đã lập chỉ mục', { n: d.vectors.total })}</span>
      </div>
      {e.error && <p className="text-bad">{e.error}</p>}
      
      {isDirty && (
        <p className="font-medium text-warn flex items-center gap-1.5 pt-1">
          ⚠️ {t('Bạn vừa thay đổi cấu hình. Vui lòng bấm "Lưu thay đổi" ở góc trên trước khi "Lập lại chỉ mục".')}
        </p>
      )}

      <div className="flex items-center gap-3 pt-1">
        <Button size="sm" onClick={() => {
          if (isDirty) {
            toast(t('Vui lòng bấm "Lưu thay đổi" ở góc trên trang trước!'), 'bad')
            return
          }
          re.mutate()
        }} loading={re.isPending || d.reindex.running}><Brain className="size-3.5" />{t('Lập lại chỉ mục')}</Button>
        {d.reindex.running && <span className="text-muted">{d.reindex.done}/{d.reindex.total}</span>}
        <span className="text-muted">{t('Cần chạy lại sau khi đổi model embedding.')}</span>
      </div>
    </div>
  )
}

export function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const onCopy = () => {
    void navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <button
      type="button"
      onClick={onCopy}
      className="flex items-center gap-1 rounded bg-panel px-2 py-1 text-[11px] font-sans text-muted border border-line transition hover:border-accent hover:text-fg"
      title={t('Sao chép lệnh')}
    >
      {copied ? <><Check className="size-3 text-ok" /><span className="text-ok font-medium">{t('Đã chép')}</span></> : <><Copy className="size-3" /><span>{t('Sao chép')}</span></>}
    </button>
  )
}

export type Mem = AppConfig['memory']
export type ProviderInfo = Record<string, { type: string; base_url: string }>

const isLocalUrl = (u: string) => /localhost|127\.0\.0\.1/.test(u)
const isGemini = (u: string) => u.includes('generativelanguage')
const LOCAL_MODELS = [
  { id: 'bge-m3', name: 'bge-m3', size: '~1,2 GB', desc: tk('Hiểu tiếng Việt tốt nhất, hợp hợp đồng, báo cáo, văn bản.'), star: true },
  { id: 'nomic-embed-text', name: 'nomic-embed-text', size: '~274 MB', desc: tk('Rất nhẹ và nhanh, hợp máy yếu hoặc không có GPU.'), star: false },
]

/** Thẻ chọn một phương án (kiểu radio, cả thẻ bấm được). */
export function Choice({ on, onClick, title, desc, badge, children }: { on: boolean; onClick: () => void; title: React.ReactNode; desc: React.ReactNode; badge?: React.ReactNode; children?: React.ReactNode }) {
  return (
    <button type="button" role="radio" aria-checked={on} onClick={onClick}
      className={`flex w-full flex-col items-start gap-1 rounded-lg border p-3 text-left transition ${on ? 'border-accent bg-accent/10' : 'border-line bg-bg hover:border-fg/30'}`}>
      <span className="flex w-full items-center gap-2 text-sm font-medium">{title}{badge}{on && <Check className="ml-auto size-4 text-accent" />}</span>
      <span className="text-xs leading-snug text-muted">{desc}</span>
      {children}
    </button>
  )
}

export function EmbeddingPanel({ memory, onChange, providerInfo, isDirty }: { memory: Mem; onChange: (patch: Partial<Mem>) => void; providerInfo: ProviderInfo; isDirty?: boolean }) {
  const q = useQuery({ queryKey: ['memory-status'], queryFn: () => api.get<MemoryStatus>('/api/memory/status') })
  const installed = q.data?.ollama_models ?? []
  const on = memory.embeddings !== 'off'
  const tab: 'local' | 'api' = memory.embeddings === 'openai' ? 'api' : 'local'
  const apiProviders = Object.entries(providerInfo).filter(([, p]) => p.type === 'openai' && !isLocalUrl(p.base_url)).map(([n, p]) => ({ name: n, gemini: isGemini(p.base_url) }))
  const gemini = apiProviders.find((p) => p.gemini)
  const cur = apiProviders.find((p) => p.name === memory.provider)
  const apiModels = cur?.gemini ? [{ id: 'gemini-embedding-001', desc: tk('Mô hình embedding của Google, hiểu tiếng Việt tốt, không cần cài gì.') }]
    : [{ id: 'text-embedding-3-small', desc: tk('Nhanh và rẻ.') }, { id: 'text-embedding-3-large', desc: tk('Chất lượng cao hơn.') }]
  const localModel = memory.model || 'bge-m3'
  const isInstalled = (m: string) => installed.some((n) => n === m || n.startsWith(m + ':'))

  const pickLocal = () => onChange({ embeddings: 'ollama', provider: null, model: tab === 'api' || !memory.model ? 'bge-m3' : memory.model })
  const pickApi = () => {
    const p = gemini ?? apiProviders[0]
    onChange({ embeddings: 'openai', provider: p?.name ?? null, model: p?.gemini ? 'gemini-embedding-001' : 'text-embedding-3-small' })
  }
  const pickProvider = (name: string) => {
    const p = apiProviders.find((x) => x.name === name)
    onChange({ provider: name || null, model: p?.gemini ? 'gemini-embedding-001' : 'text-embedding-3-small' })
  }

  return (
    <Card>
      <CardHeader title={t('Tìm kiếm theo nghĩa (embedding)')} hint={t('Giúp Argus hiểu ý câu hỏi thay vì chỉ tìm đúng từ khóa, dùng cho tài liệu và trí nhớ.')}
        action={<Switch checked={on} onChange={(v) => (v ? (tab === 'api' ? pickApi() : pickLocal()) : onChange({ embeddings: 'off' }))} label={t('Bật tìm kiếm theo nghĩa')} />} />
      {on && (
        <div className="space-y-4 p-5">
          <div className="grid gap-3 sm:grid-cols-2" role="tablist" aria-label={t('Nơi tính embedding')}>
            {([['local', Laptop, t('Trên máy bạn (Ollama)'), t('Riêng tư và miễn phí: dữ liệu không rời khỏi máy. Cần cài Ollama.'), pickLocal], ['api', Cloud, t('Gemini (đám mây)'), t('Không cần cài gì, nhanh. Các đoạn văn bản được gửi tới Google để tính.'), pickApi]] as const).map(([id, Icon, title, desc, onPick]) => (
              <button key={id} type="button" role="tab" aria-selected={tab === id} onClick={onPick}
                className={`flex items-start gap-3 rounded-xl border p-4 text-left transition ${tab === id ? 'border-accent bg-accent/10' : 'border-line bg-bg hover:border-fg/30'}`}>
                <Icon className={`mt-0.5 size-5 shrink-0 ${tab === id ? 'text-accent' : 'text-muted'}`} />
                <span><span className="block text-sm font-semibold">{title}</span><span className="mt-0.5 block text-xs leading-snug text-muted">{desc}</span></span>
              </button>
            ))}
          </div>

          {tab === 'local' ? (
            <div className="space-y-3" role="radiogroup" aria-label={t('Model embedding')}>
              <div className="grid gap-3 sm:grid-cols-2">
                {LOCAL_MODELS.map((m) => (
                  <Choice key={m.id} on={localModel === m.id} onClick={() => onChange({ model: m.id })} title={<span className="font-mono">{m.name}</span>}
                    badge={<>{m.star && <Badge tone="accent">{t('Khuyên dùng')}</Badge>}{isInstalled(m.id) ? <Badge tone="ok">{t('Đã cài')}</Badge> : <Badge>{m.size}</Badge>}</>}
                    desc={t(m.desc)} />
                ))}
              </div>
              {!isInstalled(localModel) && (
                <div className="flex flex-wrap items-center gap-3 rounded-lg border border-line bg-panel2 px-3 py-2.5 text-xs">
                  <Terminal className="size-4 shrink-0 text-accent" />
                  <span className="text-muted">{t('Chưa có model này. Mở terminal và chạy:')}</span>
                  <code className="rounded bg-bg px-2 py-1 font-mono text-[12px]">ollama pull {localModel}</code>
                  <CopyButton text={`ollama pull ${localModel}`} />
                  <a href="https://ollama.com/download" target="_blank" rel="noreferrer" className="ml-auto inline-flex items-center gap-1 text-accent hover:underline">{t('Chưa có Ollama?')}<ExternalLink className="size-3" /></a>
                </div>
              )}
              <details className="text-sm">
                <summary className="cursor-pointer select-none text-muted hover:text-fg">{t('Tùy chọn khác')}</summary>
                <div className="mt-3 grid gap-4 sm:grid-cols-2">
                  <Field label={t('Tên model khác')}><Input value={memory.model} className="font-mono" placeholder="bge-m3" list="ollama-installed" onChange={(e) => onChange({ model: e.target.value })} />
                    <datalist id="ollama-installed">{installed.map((m) => <option key={m} value={m} />)}</datalist></Field>
                  <label className="flex items-center gap-2 self-end pb-2 text-sm text-muted"><input type="checkbox" className="accent-[var(--accent)]" checked={memory.embeddings === 'hash'} onChange={(e) => onChange({ embeddings: e.target.checked ? 'hash' : 'ollama' })} />{t('Dùng chế độ offline đơn giản (không cần model, độ chính xác thấp)')}</label>
                </div>
              </details>
            </div>
          ) : apiProviders.length === 0 ? (
            <p className="rounded-lg border border-warn/40 bg-warn/10 px-3 py-2.5 text-sm text-warn">{t('Chưa có nhà cung cấp API nào. Thêm Gemini ở mục Mô hình AI rồi quay lại đây.')} <Link to="/providers" className="underline">{t('Mở Mô hình AI')}</Link></p>
          ) : (
            <div className="space-y-3">
              <Field label={t('Nhà cung cấp')}>
                <Select value={memory.provider ?? ''} onChange={(e) => pickProvider(e.target.value)}>
                  {!cur && <option value="">{t('Chọn nhà cung cấp…')}</option>}
                  {apiProviders.map((p) => <option key={p.name} value={p.name}>{p.name}{p.gemini ? ' (Gemini)' : ''}</option>)}
                </Select>
              </Field>
              <div className="grid gap-3 sm:grid-cols-2" role="radiogroup" aria-label={t('Model embedding')}>
                {apiModels.map((m) => <Choice key={m.id} on={memory.model === m.id} onClick={() => onChange({ model: m.id })} title={<span className="font-mono">{m.id}</span>} desc={t(m.desc)} />)}
              </div>
              <Field label={t('Hoặc gõ tên model khác')}><Input value={apiModels.some((m) => m.id === memory.model) ? '' : memory.model} className="font-mono" placeholder={apiModels[0].id} onChange={(e) => onChange({ model: e.target.value })} /></Field>
              <p className="rounded-lg border border-line bg-panel2 px-3 py-2 text-xs text-muted">{t('Lưu ý riêng tư: khi dùng cách này, các đoạn tài liệu và tin nhắn được lập chỉ mục sẽ được gửi tới nhà cung cấp để tính embedding.')}</p>
            </div>
          )}

          <Row title={t('Tự lập chỉ mục tin nhắn mới')}><Switch checked={memory.auto_index} onChange={(v) => onChange({ auto_index: v })} label={t('Tự lập chỉ mục')} /></Row>
          <MemoryStatusLine isDirty={isDirty} />
        </div>
      )}
    </Card>
  )
}

