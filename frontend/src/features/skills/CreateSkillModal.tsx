import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/Button'
import { Field, Input, Textarea } from '@/components/ui/Form'
import { Modal } from '@/components/ui/Modal'
import { useToast } from '@/components/ui/Toast'
import { api } from '@/lib/api'
import { errMsg } from '@/lib/utils'

export function CreateSkillModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [body, setBody] = useState('')
  const create = useMutation({
    mutationFn: () => api.post('/api/skills', { name, description, body }),
    onSuccess: () => {
      toast('Đã tạo skill')
      void qc.invalidateQueries({ queryKey: ['skills'] })
      setName(''); setDescription(''); setBody('')
      onClose()
    },
    onError: (e) => toast(errMsg(e), 'bad'),
  })
  return (
    <Modal open={open} onClose={onClose} wide title="Tạo skill mới"
      footer={<><Button onClick={onClose}>Hủy</Button><Button variant="primary" loading={create.isPending} disabled={!name || !description || !body} onClick={() => create.mutate()}>Tạo</Button></>}>
      <div className="space-y-4">
        <Field label="Tên (a-z, 0-9, - và _)"><Input value={name} onChange={(e) => setName(e.target.value.toLowerCase())} placeholder="vi-du-skill" /></Field>
        <Field label="Mô tả" hint="Luôn nằm trong prompt, viết ngắn gọn và nêu rõ khi nào nên dùng."><Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Dùng khi người dùng muốn…" /></Field>
        <Field label="Hướng dẫn (Markdown)" hint="Chỉ được nạp khi agent gọi skills_read. Dùng {baseDir} để trỏ tới thư mục của skill."><Textarea rows={10} value={body} onChange={(e) => setBody(e.target.value)} /></Field>
      </div>
    </Modal>
  )
}
