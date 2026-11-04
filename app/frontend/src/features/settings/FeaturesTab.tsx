import { Link } from 'react-router-dom'
import { Card, CardHeader } from '@/components/ui/Card'
import { Field, Input, Select } from '@/components/ui/Form'
import { Switch } from '@/components/ui/Switch'
import type { ExtraCfg } from '@/lib/types'
import { t } from '@/lib/i18n.ts'

function Row({ title, children }: { title: string; children: React.ReactNode }) {
  return <div className="-mx-5 flex items-center justify-between gap-4 border-b border-line/60 px-5 pb-4 last:border-b-0 last:pb-0 col-span-full"><p className="text-sm font-medium">{title}</p>{children}</div>
}

export function FeaturesTab({ value, onChange, providers, tools }: { value: ExtraCfg; onChange: (v: ExtraCfg) => void; providers: string[]; tools: string[] }) {
  const set = <K extends keyof ExtraCfg>(k: K, patch: Partial<ExtraCfg[K]>) => onChange({ ...value, [k]: { ...value[k], ...patch } })
  const provOpts = (blank: string) => <><option value="">{blank}</option>{providers.map((p) => <option key={p} value={p}>{p}</option>)}</>
  const { browser, media, computer, agents } = value
  return (
    <>
      <Card>
        <CardHeader title={t('Trình duyệt')} />
        <div className="grid gap-4 p-5 sm:grid-cols-2">
          <Row title={t('Bật điều khiển trình duyệt')}><Switch checked={browser.enabled} onChange={(v) => set('browser', { enabled: v })} label={t('Bật trình duyệt')} /></Row>
          <Row title={t('Chạy ẩn (không hiện cửa sổ)')}><Switch checked={browser.headless} onChange={(v) => set('browser', { headless: v })} label={t('Chạy ẩn')} disabled={!browser.enabled} /></Row>
          <Row title={t('Cho phép mở địa chỉ nội bộ')}><Switch checked={browser.allow_private} onChange={(v) => set('browser', { allow_private: v })} label={t('Cho phép địa chỉ nội bộ')} disabled={!browser.enabled} /></Row>
          <Field label={t('Đường dẫn Chromium/Chrome')}><Input value={browser.executable} className="font-mono" onChange={(e) => set('browser', { executable: e.target.value })} /></Field>
          <Field label={t('Tự đóng sau (phút không dùng)')}><Input type="number" min={1} max={240} value={browser.idle_minutes} onChange={(e) => set('browser', { idle_minutes: Number(e.target.value) })} /></Field>
        </div>
      </Card>

      <Card>
        <CardHeader title={t('Tìm kiếm theo nghĩa (embedding)')} />
        <p className="px-5 pb-4 text-sm text-muted">{t('Model embedding được cấu hình cùng các mô hình AI khác.')} <Link to="/providers?tab=embedding" className="text-accent hover:underline">{t('Mở Mô hình AI, tab Embedding')}</Link></p>
      </Card>

      <Card>
        <CardHeader title={t('Ảnh và hình ảnh')} />
        <div className="grid gap-4 p-5 sm:grid-cols-2 xl:grid-cols-3">
          <Field label={t('Provider tạo ảnh')}><Select value={media.image_provider ?? ''} onChange={(e) => set('media', { image_provider: e.target.value || null })}>{provOpts(t('Chưa chọn'))}</Select></Field>
          <Field label={t('Model tạo ảnh')}><Input value={media.image_model} className="font-mono" onChange={(e) => set('media', { image_model: e.target.value })} /></Field>
          <Field label={t('Provider để xem ảnh')}><Select value={media.vision_provider ?? ''} onChange={(e) => set('media', { vision_provider: e.target.value || null })}>{provOpts(t('Tự chọn'))}</Select></Field>
        </div>
      </Card>

      <Card>
        <CardHeader title={t('Điều khiển máy tính')} />
        <div className="space-y-3 p-5">
          <Row title={t('Bật điều khiển máy tính')}><Switch checked={computer.enabled} onChange={(v) => set('computer', { enabled: v })} label={t('Bật điều khiển máy tính')} /></Row>
          {computer.enabled && <p className="rounded-lg border border-warn/40 bg-warn/10 px-3 py-2 text-sm text-warn">{t('Cẩn thận: agent có thể bấm vào bất cứ thứ gì trên màn hình, kể cả cửa sổ chứa mật khẩu. Chỉ bật khi bạn ngồi canh, và đừng để ở chế độ Toàn quyền khi vắng mặt. Trên Linux cần xdotool (X11) hoặc ydotool + wtype (Wayland).')}</p>}
        </div>
      </Card>

      <Card>
        <CardHeader title={t('Agent con và việc dài')} />
        <div className="grid gap-4 p-5 sm:grid-cols-2 xl:grid-cols-3">
          <Field label={t('Độ sâu tối đa')}><Input type="number" min={0} max={4} value={agents.max_depth} onChange={(e) => set('agents', { max_depth: Number(e.target.value) })} /></Field>
          <Field label={t('Chạy song song')}><Input type="number" min={1} max={8} value={agents.max_parallel} onChange={(e) => set('agents', { max_parallel: Number(e.target.value) })} /></Field>
          <Field label={t('Bước tối đa cho việc nền')}><Input type="number" min={5} max={200} value={agents.task_max_steps} onChange={(e) => set('agents', { task_max_steps: Number(e.target.value) })} /></Field>
        </div>
        <details className="border-t border-line">
          <summary className="cursor-pointer select-none px-5 py-3 text-sm font-medium text-muted hover:text-fg">{t('Vai trò của agent con')}</summary>
          {Object.entries(agents.profiles).map(([name, p]) => (
            <div key={name} className="space-y-2 border-b border-line px-5 py-3 last:border-b-0">
              <div className="flex items-center gap-2"><span className="font-mono text-[13px] font-medium">{name}</span><span className="text-xs text-muted">{p.description}</span></div>
              <div className="grid gap-3 sm:grid-cols-3">
                <Field label={t('Provider')}><Select value={p.provider ?? ''} onChange={(e) => onChange({ ...value, agents: { ...agents, profiles: { ...agents.profiles, [name]: { ...p, provider: e.target.value || null } } } })}>{provOpts(t('Mặc định'))}</Select></Field>
                <Field label={t('Bước tối đa')}><Input type="number" min={1} max={100} value={p.max_steps} onChange={(e) => onChange({ ...value, agents: { ...agents, profiles: { ...agents.profiles, [name]: { ...p, max_steps: Number(e.target.value) } } } })} /></Field>
                <Field label={t('Tool được dùng')}><Input value={p.tools.join(', ')} className="font-mono" placeholder={tools.slice(0, 3).join(', ')}
                  onChange={(e) => onChange({ ...value, agents: { ...agents, profiles: { ...agents.profiles, [name]: { ...p, tools: e.target.value.split(',').map((x) => x.trim()).filter(Boolean) } } } })} /></Field>
              </div>
            </div>
          ))}
        </details>
      </Card>
    </>
  )
}
