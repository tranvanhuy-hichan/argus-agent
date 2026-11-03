import { useEffect, useState } from 'react'
import { Sparkles } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Modal } from '@/components/ui/Modal'
import { Textarea } from '@/components/ui/Form'
import { Loading, Page, PageHeader } from '@/components/ui/misc'
import { Tabs } from '@/components/ui/Tabs'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import type { Curation } from '@/lib/types'
import { errMsg } from '@/lib/utils'
import { t, tk } from '@/lib/i18n.ts'

const FILES = [
  { id: 'SOUL.md', label: 'SOUL', hint: tk('Tính cách, giọng điệu và quy tắc làm việc của agent. Luôn nằm trong prompt.') },
  { id: 'USER.md', label: 'USER', hint: tk('Thông tin về bạn (tên, sở thích, bối cảnh công việc) để agent cá nhân hóa câu trả lời.') },
  { id: 'HEARTBEAT.md', label: 'HEARTBEAT', hint: tk('Danh sách việc agent tự kiểm tra mỗi lần heartbeat (bật ở trang Tự động hóa). Mỗi dòng là một việc; xóa hết để tạm dừng.') },
  { id: 'MEMORY.md', label: 'MEMORY', hint: tk('Bộ nhớ dài hạn. Agent tự ghi vào đây khi bạn nhờ “hãy nhớ…”. Bạn có thể sửa hoặc xóa.') },
] as const

function CurateButton({ onApplied }: { onApplied: () => void }) {
  const toast = useToast()
  const [res, setRes] = useState<Curation | null>(null)
  const propose = useMutation({ mutationFn: () => api.post<Curation>('/api/memory/curate', {}), onSuccess: (r) => { if (r.ok) setRes(r); else toast(r.reason || t('Không dọn được'), 'bad') }, onError: (e) => toast(errMsg(e), 'bad') })
  const apply = useMutation({
    mutationFn: () => api.post('/api/memory/curate/apply', { new: res?.new ?? '' }),
    onSuccess: () => { toast(t('Đã áp dụng. Bản cũ được lưu thành MEMORY.md.bak-…')); setRes(null); onApplied() },
    onError: (e) => toast(errMsg(e), 'bad'),
  })
  return (
    <>
      <Button loading={propose.isPending} onClick={() => propose.mutate()}><Sparkles className="size-4" />{t('Dọn bằng AI')}</Button>
      <Modal open={!!res} onClose={() => setRes(null)} wide title={t('Đề xuất dọn trí nhớ')}
        footer={<><Button onClick={() => setRes(null)}>{t('Hủy')}</Button><Button variant="primary" loading={apply.isPending} onClick={() => apply.mutate()}>{t('Áp dụng')}</Button></>}>
        <p className="mb-3 text-sm text-muted">{t('AI gộp mục trùng, bỏ thông tin lỗi thời và sắp xếp lại. Chưa có gì bị ghi cho tới khi bạn bấm Áp dụng.')}</p>
        {res && (
          <div className="space-y-3 text-sm">
            <div><p className="mb-1 font-medium text-bad">{t('Sẽ bỏ ({n})', { n: res.removed.length })}</p>{res.removed.length ? <ul className="list-disc space-y-0.5 pl-5 text-muted">{res.removed.map((x) => <li key={x}>{x}</li>)}</ul> : <p className="text-muted">—</p>}</div>
            <div><p className="mb-1 font-medium text-ok">{t('Sẽ thêm/viết lại ({n})', { n: res.added.length })}</p>{res.added.length ? <ul className="list-disc space-y-0.5 pl-5 text-muted">{res.added.map((x) => <li key={x}>{x}</li>)}</ul> : <p className="text-muted">—</p>}</div>
          </div>
        )}
      </Modal>
    </>
  )
}

function Editor({ file, hint }: { file: string; hint: string }) {
  const qc = useQueryClient()
  const toast = useToast()
  const q = useQuery({ queryKey: ['file', file], queryFn: () => api.get<{ content: string }>(`/api/workspace/${file}`) })
  const [text, setText] = useState('')
  useEffect(() => { if (q.data) setText(q.data.content) }, [q.data])
  const save = useMutation({
    mutationFn: () => api.put(`/api/workspace/${file}`, { content: text }),
    onSuccess: () => { toast(t('Đã lưu {file}', { file })); void qc.invalidateQueries({ queryKey: ['file', file] }) },
    onError: (e) => toast(errMsg(e), 'bad'),
  })
  if (q.isLoading) return <Loading />
  return (
    <Card className="p-5">
      <p className="mb-3 text-sm text-muted">{t(hint)}</p>
      <Textarea rows={18} value={text} onChange={(e) => setText(e.target.value)} aria-label={file} />
      <div className="mt-4 flex items-center gap-3">
        <Button variant="primary" loading={save.isPending} disabled={text === q.data?.content} onClick={() => save.mutate()}>{t('Lưu')}</Button>
        {file === 'MEMORY.md' && <CurateButton onApplied={() => void qc.invalidateQueries({ queryKey: ['file', file] })} />}
        <span className="text-xs text-muted">{t('{n} ký tự', { n: text.length.toLocaleString() })}{text.length > 4000 && file !== 'SOUL.md' ? t(' · chỉ 4000 ký tự cuối được đưa vào prompt') : ''}</span>
      </div>
    </Card>
  )
}

export function WorkspacePage() {
  const [tab, setTab] = useState<(typeof FILES)[number]['id']>('SOUL.md')
  const f = FILES.find((x) => x.id === tab)!
  return (
    <Page>
      <PageHeader title={t('Không gian làm việc')} subtitle={t('Các file markdown định hình tính cách và bộ nhớ của agent.')} />
      <Tabs value={tab} onChange={setTab} tabs={FILES.map((x) => ({ id: x.id, label: x.label }))} />
      <div className="mt-5"><Editor key={f.id} file={f.id} hint={f.hint} /></div>
    </Page>
  )
}
