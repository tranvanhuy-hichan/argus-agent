import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CircleAlert, CircleCheck, ExternalLink, Trash2 } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Field, Input } from '@/components/ui/Form'
import { Modal } from '@/components/ui/Modal'
import { Loading } from '@/components/ui/misc'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import { useConfig } from '@/lib/queries'
import type { SkillDetail } from '@/lib/types'
import { errMsg } from '@/lib/utils'
import { missingText } from './SkillsPage'

export function SkillModal({ name, onClose }: { name: string | null; onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const cfg = useConfig()
  const detail = useQuery({ queryKey: ['skill', name], queryFn: () => api.get<SkillDetail>(`/api/skills/${name}`), enabled: !!name })
  const [env, setEnv] = useState<Record<string, string>>({})
  const entry = name ? cfg.data?.config.skills[name] : undefined

  useEffect(() => { setEnv(entry?.env ?? {}) }, [entry, name])

  const refresh = () => { void qc.invalidateQueries({ queryKey: ['skills'] }); void qc.invalidateQueries({ queryKey: ['config'] }); void qc.invalidateQueries({ queryKey: ['skill', name] }) }
  const saveEnv = useMutation({
    mutationFn: () => api.put(`/api/skills/${name}/config`, { enabled: entry?.enabled ?? true, api_key: entry?.api_key ?? '', env }),
    onSuccess: () => { toast('Đã lưu cấu hình skill'); refresh() },
    onError: (e) => toast(errMsg(e), 'bad'),
  })
  const remove = useMutation({
    mutationFn: () => api.del(`/api/skills/${name}`),
    onSuccess: () => { toast('Đã xóa skill'); refresh(); onClose() },
    onError: (e) => toast(errMsg(e), 'bad'),
  })

  const d = detail.data
  const envVars = d?.requires.env ?? []
  return (
    <Modal open={!!name} onClose={onClose} wide title={d ? `${d.emoji} ${d.name}`.trim() : 'Skill'}
      footer={d && (
        <>
          <Button variant="danger" onClick={() => { if (confirm(`Xóa skill "${d.name}" khỏi workspace?`)) remove.mutate() }} loading={remove.isPending}><Trash2 className="size-4" />Xóa</Button>
          <Button onClick={onClose}>Đóng</Button>
        </>
      )}
    >
      {!d ? <Loading /> : (
        <div className="space-y-5">
          <p className="text-sm text-muted">{d.description}</p>
          <div className="flex flex-wrap gap-2">
            {d.origin && <Badge tone="info">ClawHub · {d.origin.owner}/{d.origin.slug}{d.origin.version ? ` v${d.origin.version}` : ''}</Badge>}
            {d.homepage && <a href={d.homepage} target="_blank" rel="noreferrer noopener" className="inline-flex items-center gap-1 text-xs text-info hover:underline">Trang chủ <ExternalLink className="size-3" /></a>}
          </div>

          <section>
            <h3 className="mb-2 text-sm font-semibold">Điều kiện chạy</h3>
            {d.eligible ? (
              <p className="flex items-center gap-2 text-sm text-ok"><CircleCheck className="size-4" />Đã đủ điều kiện</p>
            ) : (
              <ul className="space-y-1">{d.missing.map((m) => <li key={m} className="flex items-center gap-2 text-sm text-warn"><CircleAlert className="size-4" />{missingText(m)}</li>)}</ul>
            )}
          </section>

          {envVars.length > 0 && (
            <section className="space-y-3">
              <h3 className="text-sm font-semibold">Biến môi trường</h3>
              {envVars.map((v) => (
                <Field key={v} label={v} hint={d.primary_env === v ? 'Khóa chính của skill' : undefined}>
                  <Input type="password" autoComplete="off" value={env[v] ?? ''} onChange={(e) => setEnv({ ...env, [v]: e.target.value })} placeholder="Nhập giá trị…" />
                </Field>
              ))}
              <Button variant="primary" size="sm" loading={saveEnv.isPending} onClick={() => saveEnv.mutate()}>Lưu</Button>
            </section>
          )}

          <section>
            <h3 className="mb-2 text-sm font-semibold">Nội dung SKILL.md</h3>
            <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-lg border border-line bg-bg p-3 font-mono text-xs leading-relaxed">{d.body}</pre>
            {d.files.length > 1 && <p className="mt-2 text-xs text-muted">File đi kèm: {d.files.join(', ')}</p>}
          </section>
        </div>
      )}
    </Modal>
  )
}
