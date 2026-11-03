import { useEffect, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { CircleCheck, CircleX, Plus, Trash2, Zap } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { Field, Input, Select } from '@/components/ui/Form'
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

function ProviderCard({ name, p, isDefault, models, onChange, onDelete, onMakeDefault }: {
  name: string; p: ProviderCfg; isDefault: boolean; models: string[]
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

  return (
    <Card>
      <CardHeader
        title={<span className="flex items-center gap-2">{name}<Badge>{p.type === 'anthropic' ? 'Anthropic' : 'OpenAI-compatible'}</Badge>{isDefault && <Badge tone="accent">{t('Mặc định')}</Badge>}</span>}
        action={<div className="flex gap-1.5">{!isDefault && <Button size="sm" variant="ghost" onClick={onMakeDefault}>{t('Đặt làm mặc định')}</Button>}<Button size="sm" variant="ghost" onClick={onDelete} aria-label={t('Xóa {name}', { name })}><Trash2 className="size-4" /></Button></div>}
      />
      <div className="grid gap-4 p-5 sm:grid-cols-2">
        <Field label={t('Model')} hint={<button type="button" onClick={() => { setModelsMsg(''); loadModels.mutate() }} className="text-accent hover:underline disabled:opacity-50" disabled={loadModels.isPending}>{loadModels.isPending ? t('Đang tải…') : t('Tải danh sách model')}{modelsMsg && <span className="ml-2 text-muted">· {modelsMsg}</span>}</button>}>
          <Input value={p.model} onChange={(e) => set('model', e.target.value)} list={`models-${name}`} />
          <datalist id={`models-${name}`}>{[...new Set([...fetched, ...(isOllama ? models : [])])].map((m) => <option key={m} value={m} />)}</datalist>
        </Field>
        <Field label={t('Nhiệt độ (temperature): {v}', { v: p.temperature })}>
          <input type="range" min={0} max={2} step={0.1} value={p.temperature} onChange={(e) => set('temperature', parseFloat(e.target.value))} className="mt-2 w-full accent-[var(--accent)]" />
        </Field>
        <label className="-mt-2 flex items-center gap-2 text-xs text-muted sm:col-span-2"><input type="checkbox" className="accent-[var(--accent)]" checked={allModels} onChange={(e) => setAllModels(e.target.checked)} />{t('Hiện cả model không dùng để chat (TTS, embedding, ảnh, video)')}</label>
        {p.type === 'openai' && <div className="sm:col-span-2"><Field label="Base URL"><Input value={p.base_url} onChange={(e) => set('base_url', e.target.value)} /></Field></div>}
        <Field label="API key" hint={t('Lưu trong config.json (quyền 600).')}><Input type="password" autoComplete="off" value={p.api_key} onChange={(e) => set('api_key', e.target.value)} placeholder={t('Để trống nếu dùng biến môi trường')} /></Field>
        <Field label={t('Hoặc tên biến môi trường')}><Input value={p.api_key_env} onChange={(e) => set('api_key_env', e.target.value)} placeholder="OPENAI_API_KEY" /></Field>
        <div className="grid grid-cols-2 gap-4 sm:col-span-2">
          <Field label={t('Giá vào (USD / 1 triệu token)')} hint={t('Để ước tính chi phí ở Dashboard. Bỏ trống = 0.')}><Input type="number" min={0} step={0.01} value={p.price_in ?? 0} onChange={(e) => set('price_in', Number(e.target.value))} /></Field>
          <Field label={t('Giá ra (USD / 1 triệu token)')}><Input type="number" min={0} step={0.01} value={p.price_out ?? 0} onChange={(e) => set('price_out', Number(e.target.value))} /></Field>
        </div>
        <label className="flex items-start gap-3 rounded-lg border border-line bg-panel2 p-3 text-sm sm:col-span-2">
          <input type="checkbox" className="mt-1 accent-[var(--accent)]" checked={!!p.vision} onChange={(e) => set('vision', e.target.checked)} />
          <span><span className="font-medium">{t('Model hiểu được ảnh (vision)')}</span><span className="block text-xs text-muted">{t('Bật thì ảnh bạn đính kèm trong chat được gửi trực tiếp cho model. Chỉ bật nếu model hỗ trợ.')}</span></span>
        </label>
      </div>
      <div className="flex items-center gap-3 border-t border-line px-5 py-3">
        <Button size="sm" loading={test.isPending} onClick={() => { setResult(null); test.mutate() }}><Zap className="size-3.5" />{t('Thử kết nối')}</Button>
        {result && (
          <span className={cn('flex min-w-0 items-center gap-1.5 text-xs', result.ok ? 'text-ok' : 'text-bad')}>
            {result.ok ? <CircleCheck className="size-4 shrink-0" /> : <CircleX className="size-4 shrink-0" />}
            <span className="truncate">{result.ok ? t('Hoạt động · {ms}ms · “{reply}”', { ms: result.latency_ms ?? 0, reply: result.reply ?? '' }) : result.error}</span>
          </span>
        )}
      </div>
    </Card>
  )
}

export function ProvidersPage() {
  const cfg = useConfig()
  const save = useSaveConfig()
  const toast = useToast()
  const [draft, setDraft] = useState<Pick<AppConfig, 'providers' | 'default_provider' | 'fallback'> | null>(null)
  const [preset, setPreset] = useState(Object.keys(PRESETS)[0])
  const [models, setModels] = useState<string[]>([])

  useEffect(() => {
    if (cfg.data) setDraft({ providers: cfg.data.config.providers, default_provider: cfg.data.config.default_provider, fallback: cfg.data.config.fallback })
  }, [cfg.data])
  useEffect(() => { void api.get<{ models: string[] }>('/api/ollama/models').then((r) => setModels(r.models)).catch(() => {}) }, [])

  if (cfg.error) return <Page><ErrorNote error={cfg.error} /></Page>
  if (!draft || !cfg.data) return <Loading />
  const names = Object.keys(draft.providers)
  const dirty = JSON.stringify(draft) !== JSON.stringify({ providers: cfg.data.config.providers, default_provider: cfg.data.config.default_provider, fallback: cfg.data.config.fallback })

  const add = () => {
    const base = preset.split(' ')[0].toLowerCase().replace(/[^a-z0-9]/g, '')
    let n = base, i = 2
    while (draft.providers[n]) n = `${base}${i++}`
    setDraft({ ...draft, providers: { ...draft.providers, [n]: { ...PRESETS[preset] } } })
  }
  const remove = (n: string) => {
    if (names.length < 2) return toast(t('Cần ít nhất một provider'), 'bad')
    const { [n]: _, ...rest } = draft.providers
    const left = Object.keys(rest)
    setDraft({ providers: rest, default_provider: draft.default_provider === n ? left[0] : draft.default_provider, fallback: draft.fallback.filter((f) => f !== n) })
  }
  const onSave = () => save.mutate({ ...cfg.data.config, ...draft }, { onSuccess: () => toast(t('Đã lưu providers')), onError: (e) => toast(errMsg(e), 'bad') })

  return (
    <Page>
      <PageHeader title={t('Nhà cung cấp')} subtitle={t('Kết nối model local (Ollama) hoặc bất kỳ API nào tương thích OpenAI, cùng Claude.')} action={<Button variant="primary" disabled={!dirty} loading={save.isPending} onClick={onSave}>{t('Lưu thay đổi')}</Button>} />
      <div className="space-y-4">
        <Card>
          <CardHeader title={t('Dự phòng (fallback)')} hint={t('Khi provider đang dùng lỗi, agent tự thử lần lượt các provider được chọn.')} />
          <div className="flex flex-wrap gap-x-5 gap-y-2 p-5">
            {names.filter((n) => n !== draft.default_provider).map((n) => (
              <label key={n} className="flex items-center gap-2 text-sm">
                <input type="checkbox" className="accent-[var(--accent)]" checked={draft.fallback.includes(n)} onChange={(e) => setDraft({ ...draft, fallback: e.target.checked ? [...draft.fallback, n] : draft.fallback.filter((f) => f !== n) })} />{n}
              </label>
            ))}
            {names.length < 2 && <p className="text-sm text-muted">{t('Thêm provider thứ hai để dùng làm dự phòng.')}</p>}
          </div>
        </Card>
        {names.map((n) => (
          <ProviderCard key={n} name={n} p={draft.providers[n]} isDefault={n === draft.default_provider} models={models}
            onChange={(p) => setDraft({ ...draft, providers: { ...draft.providers, [n]: p } })} onDelete={() => remove(n)} onMakeDefault={() => setDraft({ ...draft, default_provider: n, fallback: draft.fallback.filter((f) => f !== n) })} />
        ))}
        <Card className="flex flex-wrap items-center gap-3 p-4">
          <Select value={preset} onChange={(e) => setPreset(e.target.value)} className="w-64" aria-label={t('Mẫu provider')}>{Object.keys(PRESETS).map((p) => <option key={p} value={p}>{t(p)}</option>)}</Select>
          <Button onClick={add}><Plus className="size-4" />{t('Thêm provider')}</Button>
        </Card>
      </div>
    </Page>
  )
}
