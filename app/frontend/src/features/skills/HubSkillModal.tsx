import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, ShieldAlert, ShieldCheck } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
import { ErrorNote, Loading } from '@/components/ui/misc'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import type { HubDetail, HubSkill, Skill } from '@/lib/types'
import { errMsg, fmtNum } from '@/lib/utils'
import { t } from '@/lib/i18n.ts'

export function HubSkillModal({ skill, installed, onClose }: { skill: HubSkill | null; installed: boolean; onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const detail = useQuery({
    queryKey: ['hub-skill', skill?.owner, skill?.slug],
    queryFn: () => api.get<HubDetail>(`/api/clawhub/skill?slug=${encodeURIComponent(skill!.slug)}&owner=${encodeURIComponent(skill!.owner)}`),
    enabled: !!skill,
  })
  const install = useMutation({
    mutationFn: () => api.post<{ skill: Skill; suspicious: boolean }>('/api/clawhub/install', { slug: skill!.slug, owner: skill!.owner, overwrite: installed }),
    onSuccess: (r) => {
      toast(r.skill.eligible ? t('Đã cài {name}', { name: r.skill.name }) : t('Đã cài {name} — cần thiết lập thêm trong tab Đã cài', { name: r.skill.name }))
      void qc.invalidateQueries({ queryKey: ['skills'] })
      onClose()
    },
    onError: (e) => toast(errMsg(e), 'bad'),
  })

  const d = detail.data
  const flagged = d?.moderation?.isSuspicious
  const blocked = d?.moderation?.isMalwareBlocked || (d && !d.installable)
  return (
    <Modal open={!!skill} onClose={onClose} wide title={skill ? `${skill.name} · @${skill.owner}` : ''}
      footer={
        <>
          <Button onClick={onClose}>{t('Đóng')}</Button>
          <Button variant="primary" disabled={!d || !!blocked} loading={install.isPending} onClick={() => install.mutate()}>
            <Download className="size-4" />{installed ? t('Cài lại / cập nhật') : t('Cài đặt')}
          </Button>
        </>
      }
    >
      {detail.isLoading ? <Loading /> : detail.error ? <ErrorNote error={detail.error} /> : d && (
        <div className="space-y-4">
          <p className="text-sm text-muted">{d.summary}</p>
          <div className="flex flex-wrap items-center gap-2">
            {d.version && <Badge>v{d.version}</Badge>}
            <Badge><Download className="size-3" />{fmtNum(d.downloads)}</Badge>
            {d.license && <Badge>{d.license}</Badge>}
            {installed && <Badge tone="ok">{t('Đã cài')}</Badge>}
            {blocked ? <Badge tone="bad"><ShieldAlert className="size-3" />{t('Bị chặn')}</Badge> : flagged ? <Badge tone="warn"><ShieldAlert className="size-3" />{t('Bị gắn cờ đáng ngờ')}</Badge> : <Badge tone="ok"><ShieldCheck className="size-3" />{t('Chưa có cảnh báo')}</Badge>}
          </div>
          {(flagged || blocked) && <p className="rounded-lg border border-warn/30 bg-warn/10 px-3 py-2 text-sm text-warn">{d.moderation?.summary || t('ClawHub đã gắn cờ skill này. Không nên cài nếu bạn không hiểu rõ nội dung.')}</p>}
          <p className="rounded-lg border border-line bg-panel2 px-3 py-2 text-xs text-muted">
            {t('Skill chỉ là văn bản hướng dẫn cho agent, nhưng hướng dẫn đó có thể bảo agent chạy lệnh hoặc gọi API. Lệnh shell vẫn cần bạn bấm “Cho phép” (khi bật xác nhận). Hãy đọc nội dung bên dưới trước khi cài.')}
          </p>
          {d.changelog && <p className="text-xs text-muted">{t('Nhật ký thay đổi')}: {d.changelog}</p>}
          <section>
            <h3 className="mb-2 text-sm font-semibold">SKILL.md</h3>
            <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-lg border border-line bg-bg p-3 font-mono text-xs leading-relaxed">{d.skill_md ?? t('(không xem trước được)')}</pre>
          </section>
        </div>
      )}
    </Modal>
  )
}
