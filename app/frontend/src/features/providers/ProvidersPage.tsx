import { useEffect, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { ChevronDown, CircleCheck, CircleX, KeyRound, Plus, Star, Trash2, Zap } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { BrandIcon, type Brand } from '@/components/ui/BrandIcon'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Field, Input } from '@/components/ui/Form'
import { ErrorNote, Loading, Page, PageHeader } from '@/components/ui/misc'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import { useConfig, useSaveConfig } from '@/lib/queries'
import type { AppConfig, ProviderCfg } from '@/lib/types'
import { cn, errMsg } from '@/lib/utils'
import { t, tk } from '@/lib/i18n.ts'

const openai = (base_url: string, model: string, api_key_env = ''): ProviderCfg => ({ type: 'openai', base_url, model, api_key: '', api_key_env, temperature: 0.7 })
// Model mac dinh chi la goi y; bam "Tai danh sach" de lay model that tu nha cung cap.
const CUSTOM = tk('Tùy chỉnh (OpenAI-compatible)')
const PRESETS: Record<string, ProviderCfg> = {
  'Ollama (local)': openai('http://localhost:11434/v1', 'qwen2.5:3b'),
  'LM Studio (local)': openai('http://localhost:1234/v1', 'local-model'),
  'vLLM / llama.cpp (local)': openai('http://localhost:8000/v1', 'local-model'),
  'Google Gemini': openai('https://generativelanguage.googleapis.com/v1beta/openai/', 'gemini-2.5-flash', 'GEMINI_API_KEY'),
  'Anthropic (Claude)': { type: 'anthropic', base_url: '', model: 'claude-sonnet-5-5', api_key: '', api_key_env: 'ANTHROPIC_API_KEY', temperature: 0.7 },
  OpenAI: openai('https://api.openai.com/v1', 'gpt-4o-mini', 'OPENAI_API_KEY'),
  OpenRouter: openai('https://openrouter.ai/api/v1', 'openai/gpt-4o-mini', 'OPENROUTER_API_KEY'),
  DeepSeek: openai('https://api.deepseek.com/v1', 'deepseek-chat', 'DEEPSEEK_API_KEY'),
  'Mistral AI': openai('https://api.mistral.ai/v1', 'mistral-small-latest', 'MISTRAL_API_KEY'),
  'xAI (Grok)': openai('https://api.x.ai/v1', 'grok-4', 'XAI_API_KEY'),
  Groq: openai('https://api.groq.com/openai/v1', 'llama-3.3-70b-versatile', 'GROQ_API_KEY'),
  Cerebras: openai('https://api.cerebras.ai/v1', 'llama-3.3-70b', 'CEREBRAS_API_KEY'),
  'Together AI': openai('https://api.together.xyz/v1', 'meta-llama/Llama-3.3-70B-Instruct-Turbo', 'TOGETHER_API_KEY'),
  'Fireworks AI': openai('https://api.fireworks.ai/inference/v1', 'accounts/fireworks/models/llama-v3p3-70b-instruct', 'FIREWORKS_API_KEY'),
  'Alibaba Qwen (DashScope)': openai('https://dashscope-intl.aliyuncs.com/compatible-mode/v1', 'qwen-plus', 'DASHSCOPE_API_KEY'),
  [CUSTOM]: openai('http://', ''),
}

type TestResult = { ok: boolean; reply?: string; error?: string; latency_ms?: number }

/** Dich vu hien o muc "Them mo hinh AI": nhom, mo ta ngan cho nguoi khong chuyen, va mau cau hinh. */
const SERVICES: { preset: string; label: string; desc: string; group: 'local' | 'cloud'; brand: Brand | null }[] = [
  { preset: 'Ollama (local)', label: 'Ollama', desc: tk('Chạy ngay trên máy bạn, miễn phí, không gửi dữ liệu đi đâu.'), group: 'local', brand: 'ollama' },
  { preset: 'LM Studio (local)', label: 'LM Studio', desc: tk('Phần mềm chạy model trên máy bạn, có giao diện dễ dùng.'), group: 'local', brand: 'lmstudio' },
  { preset: 'Google Gemini', label: 'Google Gemini', desc: tk('Mạnh, nhanh, có hạn mức dùng thử. Dễ bắt đầu nhất.'), group: 'cloud', brand: 'gemini' },
  { preset: 'Anthropic (Claude)', label: 'Claude', desc: tk('Của Anthropic. Rất tốt cho viết lách và lập trình.'), group: 'cloud', brand: 'claude' },
  { preset: 'OpenAI', label: 'OpenAI (ChatGPT)', desc: tk('Dịch vụ phổ biến nhất, nhiều model để chọn.'), group: 'cloud', brand: 'openai' },
  { preset: 'DeepSeek', label: 'DeepSeek', desc: tk('Giá rẻ, mạnh về suy luận và code.'), group: 'cloud', brand: 'deepseek' },
  { preset: 'OpenRouter', label: 'OpenRouter', desc: tk('Một khóa dùng được hàng trăm model của nhiều hãng.'), group: 'cloud', brand: 'openrouter' },
  { preset: 'Groq', label: 'Groq', desc: tk('Trả lời cực nhanh.'), group: 'cloud', brand: 'groq' },
  { preset: CUSTOM, label: tk('Dịch vụ khác'), desc: tk('Bất kỳ dịch vụ nào tương thích OpenAI (nhập địa chỉ và khóa).'), group: 'cloud', brand: null },
]
// Cac dich vu chi nam trong "Xem them": van co logo hang.
const EXTRA_BRANDS: Record<string, Brand> = { 'vLLM / llama.cpp (local)': 'vllm', 'Mistral AI': 'mistral', 'xAI (Grok)': 'xai', Cerebras: 'cerebras', 'Together AI': 'together', 'Fireworks AI': 'fireworks', 'Alibaba Qwen (DashScope)': 'qwen' }
const OTHER_PRESETS = Object.keys(PRESETS).filter((k) => !SERVICES.some((s) => s.preset === k))

const isLocal = (p: ProviderCfg) => /localhost|127\.0\.0\.1/.test(p.base_url)
const brandOf = (p: ProviderCfg): Brand | null => {
  const hit = Object.entries(PRESETS).find(([, c]) => c.base_url === p.base_url && c.type === p.type)?.[0]
  return hit ? (EXTRA_BRANDS[hit] ?? null) : null
}
const hasKey = (p: ProviderCfg) => !!p.api_key || !!p.api_key_env

function ProviderCard({ name, p, isDefault, models, open, onToggle, onChange, onDelete, onMakeDefault }: {
  name: string; p: ProviderCfg; isDefault: boolean; models: string[]; open: boolean; onToggle: () => void
  onChange: (p: ProviderCfg) => void; onDelete: () => void; onMakeDefault: () => void
}) {
  const [result, setResult] = useState<TestResult | null>(null)
  const [fetched, setFetched] = useState<string[]>([])
  const [modelsMsg, setModelsMsg] = useState('')
  const [allModels, setAllModels] = useState(false)
  const test = useMutation({ mutationFn: () => api.post<TestResult>(`/api/providers/${name}/test`, { provider: p }), onSuccess: setResult, onError: (e) => setResult({ ok: false, error: errMsg(e) }) })
  const loadModels = useMutation({
    mutationFn: () => api.post<{ ok: boolean; models: string[]; error?: string }>(`/api/providers/models?all_models=${allModels}`, { provider: p }),
    onSuccess: (r) => { setFetched(r.models); setModelsMsg(r.ok ? t('{n} model', { n: r.models.length }) : r.error ?? t('lỗi')) },
    onError: (e) => setModelsMsg(errMsg(e)),
  })
  const set = <K extends keyof ProviderCfg>(k: K, v: ProviderCfg[K]) => onChange({ ...p, [k]: v })
  const isOllama = p.type === 'openai' && p.base_url.includes('11434')
  const needsKey = !isLocal(p) && !hasKey(p)
  const svc = SERVICES.find((x) => PRESETS[x.preset]?.base_url === p.base_url && PRESETS[x.preset]?.type === p.type)

  return (
    <Card className={cn(isDefault && 'border-accent/50')}>
      <div className="flex items-start gap-3 p-4">
        <div className="grid size-10 shrink-0 place-items-center rounded-xl bg-panel2"><BrandIcon brand={svc?.brand ?? brandOf(p)} /></div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold">{name}</span>
            {isDefault && <Badge tone="accent"><Star className="size-3" />{t('Đang dùng chính')}</Badge>}
            {needsKey ? <Badge tone="warn"><KeyRound className="size-3" />{t('Cần khóa API')}</Badge> : isLocal(p) ? <Badge>{t('Chạy trên máy bạn')}</Badge> : <Badge tone="ok">{t('Đã có khóa')}</Badge>}
          </div>
          <p className="mt-0.5 truncate font-mono text-xs text-muted">{p.model || t('(chưa chọn model)')}</p>
        </div>
        {!isDefault && <Button size="sm" variant="ghost" onClick={onMakeDefault}>{t('Dùng làm chính')}</Button>}
        <Button size="sm" variant="ghost" onClick={onDelete} aria-label={t('Xóa {name}', { name })}><Trash2 className="size-4" /></Button>
      </div>
      <div className="flex flex-wrap items-center gap-3 border-t border-line px-4 py-2.5">
        <Button size="sm" loading={test.isPending} onClick={() => { setResult(null); test.mutate() }}><Zap className="size-3.5" />{t('Thử kết nối')}</Button>
        <Button size="sm" variant="ghost" onClick={onToggle} aria-expanded={open}><ChevronDown className={cn('size-3.5 transition', open && 'rotate-180')} />{t('Chỉnh sửa')}</Button>
        {result && (
          <span className={cn('flex min-w-0 items-center gap-1.5 text-xs', result.ok ? 'text-ok' : 'text-bad')}>
            {result.ok ? <CircleCheck className="size-4 shrink-0" /> : <CircleX className="size-4 shrink-0" />}
            <span className="truncate">{result.ok ? t('Hoạt động · {ms}ms · “{reply}”', { ms: result.latency_ms ?? 0, reply: result.reply ?? '' }) : result.error}</span>
          </span>
        )}
      </div>
      {open && (
        <div className="space-y-4 border-t border-line p-4">
          <div className="grid gap-4 lg:grid-cols-2">
            {p.type === 'anthropic' || !isLocal(p) ? (
              <Field label={t('Khóa API')} hint={needsKey ? t('Dán khóa lấy từ trang của nhà cung cấp. Khóa được mã hóa khi lưu.') : t('Đã lưu. Để nguyên nếu không đổi.')}>
                <Input type="password" autoComplete="off" value={p.api_key} onChange={(e) => set('api_key', e.target.value)} placeholder={t('Dán khóa API vào đây')} />
              </Field>
            ) : <div />}
            <Field label={t('Model')} hint={<button type="button" onClick={() => { setModelsMsg(''); loadModels.mutate() }} className="text-accent hover:underline disabled:opacity-50" disabled={loadModels.isPending}>{loadModels.isPending ? t('Đang tải…') : t('Xem các model có sẵn')}{modelsMsg && <span className="ml-2 text-muted">· {modelsMsg}</span>}</button>}>
              <Input value={p.model} onChange={(e) => set('model', e.target.value)} list={`models-${name}`} />
              <datalist id={`models-${name}`}>{[...new Set([...fetched, ...(isOllama ? models : [])])].map((m) => <option key={m} value={m} />)}</datalist>
            </Field>
          </div>
          <label className="flex items-start gap-3 rounded-lg border border-line bg-panel2 p-3 text-sm">
            <input type="checkbox" className="mt-1 accent-[var(--accent)]" checked={!!p.vision} onChange={(e) => set('vision', e.target.checked)} />
            <span><span className="font-medium">{t('Model hiểu được ảnh (vision)')}</span><span className="block text-xs text-muted">{t('Bật thì ảnh bạn đính kèm trong chat được gửi trực tiếp cho model. Chỉ bật nếu model hỗ trợ.')}</span></span>
          </label>
          <details>
            <summary className="cursor-pointer select-none text-sm text-muted hover:text-fg">{t('Tùy chọn nâng cao')}</summary>
            <div className="mt-3 grid gap-4 lg:grid-cols-2">
              {p.type === 'openai' && <div className="lg:col-span-2"><Field label={t('Địa chỉ máy chủ (Base URL)')}><Input value={p.base_url} onChange={(e) => set('base_url', e.target.value)} className="font-mono" /></Field></div>}
              <Field label={t('Hoặc lấy khóa từ biến môi trường')}><Input value={p.api_key_env} onChange={(e) => set('api_key_env', e.target.value)} placeholder="OPENAI_API_KEY" className="font-mono" /></Field>
              <Field label={t('Độ sáng tạo (temperature): {v}', { v: p.temperature })} hint={t('Thấp = chắc chắn, cao = bay bổng. 0.7 là hợp lý.')}>
                <input type="range" min={0} max={2} step={0.1} value={p.temperature} onChange={(e) => set('temperature', parseFloat(e.target.value))} className="mt-2 w-full accent-[var(--accent)]" />
              </Field>
              <Field label={t('Giá vào (USD / 1 triệu token)')} hint={t('Chỉ để ước tính chi phí ở trang Thống kê. Bỏ trống = 0.')}><Input type="number" min={0} step={0.01} value={p.price_in ?? 0} onChange={(e) => set('price_in', Number(e.target.value))} /></Field>
              <Field label={t('Giá ra (USD / 1 triệu token)')}><Input type="number" min={0} step={0.01} value={p.price_out ?? 0} onChange={(e) => set('price_out', Number(e.target.value))} /></Field>
              <label className="flex items-center gap-2 text-xs text-muted lg:col-span-2"><input type="checkbox" className="accent-[var(--accent)]" checked={allModels} onChange={(e) => setAllModels(e.target.checked)} />{t('Khi xem model, hiện cả loại không dùng để chat (giọng nói, embedding, ảnh, video)')}</label>
            </div>
          </details>
        </div>
      )}
    </Card>
  )
}

function Tile({ brand, label, desc, onClick }: { brand: Brand | null; label: string; desc: string; onClick: () => void }) {
  return (
    <button onClick={onClick} className="flex items-start gap-3 rounded-xl border border-line bg-panel p-4 text-left transition hover:border-accent/60">
      <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-panel2">{brand ? <BrandIcon brand={brand} /> : <Plus className="size-5 text-muted" />}</span>
      <span className="min-w-0"><span className="block font-medium">{label}</span><span className="mt-0.5 block text-xs text-muted">{desc}</span></span>
    </button>
  )
}

export function ProvidersPage() {
  const cfg = useConfig()
  const save = useSaveConfig()
  const toast = useToast()
  const [draft, setDraft] = useState<Pick<AppConfig, 'providers' | 'default_provider' | 'fallback'> | null>(null)
  const [models, setModels] = useState<string[]>([])
  const [openCards, setOpenCards] = useState<Set<string>>(new Set())

  useEffect(() => {
    if (cfg.data) setDraft({ providers: cfg.data.config.providers, default_provider: cfg.data.config.default_provider, fallback: cfg.data.config.fallback })
  }, [cfg.data])
  useEffect(() => { void api.get<{ models: string[] }>('/api/ollama/models').then((r) => setModels(r.models)).catch(() => {}) }, [])

  if (cfg.error) return <Page><ErrorNote error={cfg.error} /></Page>
  if (!draft || !cfg.data) return <Loading />
  const names = Object.keys(draft.providers)
  const dirty = JSON.stringify(draft) !== JSON.stringify({ providers: cfg.data.config.providers, default_provider: cfg.data.config.default_provider, fallback: cfg.data.config.fallback })
  const toggle = (n: string) => setOpenCards((s) => { const x = new Set(s); if (x.has(n)) x.delete(n); else x.add(n); return x })

  const add = (preset: string) => {
    const base = preset.split(' ')[0].toLowerCase().replace(/[^a-z0-9]/g, '') || 'custom'
    let n = base, i = 2
    while (draft.providers[n]) n = `${base}${i++}`
    setDraft({ ...draft, providers: { ...draft.providers, [n]: { ...PRESETS[preset] } } })
    setOpenCards((s) => new Set(s).add(n))
    toast(t('Đã thêm {name}. Điền khóa API rồi bấm Lưu thay đổi.', { name: n }))
  }
  const remove = (n: string) => {
    if (names.length < 2) return toast(t('Cần ít nhất một mô hình'), 'bad')
    const { [n]: _, ...rest } = draft.providers
    const left = Object.keys(rest)
    setDraft({ providers: rest, default_provider: draft.default_provider === n ? left[0] : draft.default_provider, fallback: draft.fallback.filter((f) => f !== n) })
  }
  const onSave = () => save.mutate({ ...cfg.data.config, ...draft }, { onSuccess: () => toast(t('Đã lưu')), onError: (e) => toast(errMsg(e), 'bad') })
  const others = names.filter((n) => n !== draft.default_provider)

  return (
    <Page>
      <PageHeader title={t('Mô hình AI')} subtitle={t('Đây là “bộ não” của agent. Chọn một dịch vụ, dán khóa là dùng được. Bạn có thể thêm nhiều mô hình và đổi qua lại bất cứ lúc nào.')}
        action={<Button variant="primary" disabled={!dirty} loading={save.isPending} onClick={onSave}>{t('Lưu thay đổi')}</Button>} />

      <section className="mb-8">
        <h2 className="mb-3 text-sm font-semibold">{t('Mô hình của bạn')}</h2>
        <div className="grid items-start gap-3 xl:grid-cols-2">
          {names.map((n) => (
            <ProviderCard key={n} name={n} p={draft.providers[n]} isDefault={n === draft.default_provider} models={models} open={openCards.has(n)} onToggle={() => toggle(n)}
              onChange={(p) => setDraft({ ...draft, providers: { ...draft.providers, [n]: p } })} onDelete={() => remove(n)}
              onMakeDefault={() => setDraft({ ...draft, default_provider: n, fallback: draft.fallback.filter((f) => f !== n) })} />
          ))}
        </div>
      </section>

      <section className="mb-8">
        <h2 className="text-sm font-semibold">{t('Thêm mô hình AI')}</h2>
        <p className="mb-3 mt-0.5 text-xs text-muted">{t('Bấm vào một dịch vụ để thêm. Dịch vụ đám mây cần khóa API (lấy trên trang của họ); loại chạy trên máy bạn thì không cần.')}</p>
        {(['local', 'cloud'] as const).map((g) => (
          <div key={g} className="mb-4">
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted/80">{g === 'local' ? t('Chạy trên máy bạn') : t('Dịch vụ đám mây')}</p>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {SERVICES.filter((x) => x.group === g).map((x) => <Tile key={x.preset} brand={x.brand} label={t(x.label)} desc={t(x.desc)} onClick={() => add(x.preset)} />)}
            </div>
          </div>
        ))}
        <details>
          <summary className="cursor-pointer select-none text-xs text-muted hover:text-fg">{t('Xem thêm dịch vụ')}</summary>
          <div className="mt-2 flex flex-wrap gap-2">{OTHER_PRESETS.map((k) => <Button key={k} size="sm" onClick={() => add(k)}><BrandIcon brand={EXTRA_BRANDS[k]} className="size-4" />{t(k)}</Button>)}</div>
        </details>
      </section>

      {others.length > 0 && (
        <Card className="p-5">
          <h2 className="text-sm font-semibold">{t('Mô hình dự phòng')}</h2>
          <p className="mb-3 mt-0.5 text-xs text-muted">{t('Nếu mô hình chính bị lỗi hoặc quá tải, agent tự chuyển sang các mô hình bạn tick dưới đây, theo thứ tự.')}</p>
          <div className="flex flex-wrap gap-x-5 gap-y-2">
            {others.map((n) => (
              <label key={n} className="flex items-center gap-2 text-sm">
                <input type="checkbox" className="accent-[var(--accent)]" checked={draft.fallback.includes(n)} onChange={(e) => setDraft({ ...draft, fallback: e.target.checked ? [...draft.fallback, n] : draft.fallback.filter((f) => f !== n) })} />{n}
              </label>
            ))}
          </div>
        </Card>
      )}
    </Page>
  )
}
