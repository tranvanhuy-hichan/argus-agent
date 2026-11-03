import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Textarea } from '@/components/ui/Form'
import { Loading, Page, PageHeader } from '@/components/ui/misc'
import { Tabs } from '@/components/ui/Tabs'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import { errMsg } from '@/lib/utils'

const FILES = [
  { id: 'SOUL.md', label: 'SOUL', hint: 'Tính cách, giọng điệu và quy tắc làm việc của agent. Luôn nằm trong prompt.' },
  { id: 'USER.md', label: 'USER', hint: 'Thông tin về bạn (tên, sở thích, bối cảnh công việc) để agent cá nhân hóa câu trả lời.' },
  { id: 'MEMORY.md', label: 'MEMORY', hint: 'Bộ nhớ dài hạn. Agent tự ghi vào đây khi bạn nhờ “hãy nhớ…”. Bạn có thể sửa hoặc xóa.' },
] as const

function Editor({ file, hint }: { file: string; hint: string }) {
  const qc = useQueryClient()
  const toast = useToast()
  const q = useQuery({ queryKey: ['file', file], queryFn: () => api.get<{ content: string }>(`/api/workspace/${file}`) })
  const [text, setText] = useState('')
  useEffect(() => { if (q.data) setText(q.data.content) }, [q.data])
  const save = useMutation({
    mutationFn: () => api.put(`/api/workspace/${file}`, { content: text }),
    onSuccess: () => { toast(`Đã lưu ${file}`); void qc.invalidateQueries({ queryKey: ['file', file] }) },
    onError: (e) => toast(errMsg(e), 'bad'),
  })
  if (q.isLoading) return <Loading />
  return (
    <Card className="p-5">
      <p className="mb-3 text-sm text-muted">{hint}</p>
      <Textarea rows={18} value={text} onChange={(e) => setText(e.target.value)} aria-label={file} />
      <div className="mt-4 flex items-center gap-3">
        <Button variant="primary" loading={save.isPending} disabled={text === q.data?.content} onClick={() => save.mutate()}>Lưu</Button>
        <span className="text-xs text-muted">{text.length.toLocaleString()} ký tự{text.length > 4000 && file !== 'SOUL.md' ? ' · chỉ 4000 ký tự cuối được đưa vào prompt' : ''}</span>
      </div>
    </Card>
  )
}

export function WorkspacePage() {
  const [tab, setTab] = useState<(typeof FILES)[number]['id']>('SOUL.md')
  const f = FILES.find((x) => x.id === tab)!
  return (
    <Page>
      <PageHeader title="Workspace" subtitle="Các file markdown định hình agent, giống cách OpenClaw tổ chức workspace." />
      <Tabs value={tab} onChange={setTab} tabs={FILES.map((x) => ({ id: x.id, label: x.label }))} />
      <div className="mt-5"><Editor key={f.id} file={f.id} hint={f.hint} /></div>
    </Page>
  )
}
