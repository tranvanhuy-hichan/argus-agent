import { Fragment, useState, type ReactNode } from 'react'
import { Check, Copy, Download, FileText } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
import { ErrorNote, Loading } from '@/components/ui/misc'
import { api } from '@/lib/api'
import { t, useLang } from '@/lib/i18n.ts'

function Code({ code, lang }: { code: string; lang: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <div className="my-2 overflow-hidden rounded-lg border border-line bg-bg">
      <div className="flex items-center justify-between border-b border-line px-3 py-1 text-[11px] text-muted">
        <span>{lang || 'code'}</span>
        <button
          onClick={() => {
            void navigator.clipboard.writeText(code).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500) })
          }}
          className="flex items-center gap-1 hover:text-fg"
        >
          {copied ? <Check className="size-3" /> : <Copy className="size-3" />}{copied ? t('Đã chép') : t('Chép')}
        </button>
      </div>
      <pre className="overflow-x-auto p-3 font-mono text-[12.5px] leading-relaxed"><code>{code}</code></pre>
    </div>
  )
}

/** Thẻ nguồn của kho tài liệu: [[src:id|tên file|vị trí]] hiện thành chip nhỏ; bấm để xem đúng đoạn trích trong một thẻ, tải file gốc là tùy chọn. */
function SourceChip({ id, name, loc }: { id: string; name: string; loc: string }) {
  const lang = useLang()
  const [open, setOpen] = useState(false)
  const shown = lang === 'en' ? loc.replace(/^trang /, 'page ').replace(/d\u00f2ng /, 'rows ').replace(/^m\u1ee5c /, 'section ').replace(/^\u0111o\u1ea1n /, 'paragraphs ') : loc
  const ext = /\.[A-Za-z0-9]{2,5}$/.exec(name)?.[0] ?? ''
  const base = name.slice(0, name.length - ext.length)
  const short = base.length > 24 ? `${base.slice(0, 22)}…${ext}` : name
  const passage = useQuery({ queryKey: ['kb-passage', id, loc], queryFn: () => api.get<{ text: string; truncated: boolean; has_file: boolean }>(`/api/knowledge/${id}/passage?loc=${encodeURIComponent(loc)}`), enabled: open, staleTime: 600_000 })
  return (
    <>
      <button type="button" onClick={() => setOpen(true)} title={`${name} · ${loc}`}
        className="mx-0.5 inline-flex max-w-full translate-y-[-1px] items-center gap-1 rounded-md border border-line bg-panel2 px-1.5 py-px align-middle text-[11px] leading-5 text-muted transition hover:border-accent/60 hover:text-fg">
        <FileText className="size-3 shrink-0" /><span className="truncate">{short}</span><span className="shrink-0 text-accent">{shown}</span>
      </button>
      <Modal open={open} onClose={() => setOpen(false)} wide title={<span className="flex min-w-0 items-center gap-2"><FileText className="size-4 shrink-0 text-muted" /><span className="truncate">{name}</span><span className="shrink-0 text-sm font-normal text-accent">{shown}</span></span>}
        footer={<>
          <Button onClick={() => setOpen(false)}>{t('Đóng')}</Button>
          {passage.data?.has_file && <a href={`/api/knowledge/${id}/file`} target="_blank" rel="noreferrer noopener"><Button><Download className="size-4" />{t('Tải file gốc')}</Button></a>}
        </>}>
        {passage.isLoading ? <Loading /> : passage.error ? <ErrorNote error={passage.error} /> : passage.data && (
          <div>
            <p className="whitespace-pre-wrap break-words text-sm leading-relaxed">{passage.data.text || t('(không có nội dung)')}</p>
            {passage.data.truncated && <p className="mt-3 text-xs text-muted">{t('Đoạn trích dài nên chỉ hiện phần đầu. Tải file gốc để xem đầy đủ.')}</p>}
          </div>
        )}
      </Modal>
    </>
  )
}

function inline(text: string): ReactNode[] {
  const re = /(`[^`\n]+`|\*\*[^*\n]+\*\*|\[\[src:[^\]\n]+\]\]|\[[^\]\n]+\]\(https?:\/\/[^)\s]+\)|(?<![*\w])\*[^*\s][^*\n]*?\*(?![*\w]))/g
  return text.split(re).map((part, i) => {
    const src = /^\[\[src:([^|\]]+)\|([^|\]]+)\|([^\]]+)\]\]$/.exec(part)
    if (src) return <SourceChip key={i} id={src[1].trim()} name={src[2].trim()} loc={src[3].trim()} />
    if (/^\*[^*\s][^*\n]*\*$/.test(part)) return <em key={i}>{part.slice(1, -1)}</em>
    if (part.startsWith('`') && part.endsWith('`') && part.length > 2) return <code key={i} className="rounded bg-panel2 px-1 py-0.5 font-mono text-[12.5px]">{part.slice(1, -1)}</code>
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) return <strong key={i}>{part.slice(2, -2)}</strong>
    const link = /^\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)$/.exec(part)
    if (link) return <a key={i} href={link[2]} target="_blank" rel="noreferrer noopener" className="text-info underline underline-offset-2">{link[1]}</a>
    return <Fragment key={i}>{part}</Fragment>
  })
}

const isRow = (l: string) => /^\s*\|.*\|\s*$/.test(l)
const isSeparator = (l: string) => isRow(l) && l.replace(/[|\s:-]/g, '') === '' && l.includes('-')
const cells = (l: string) => l.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim())

function Table({ head, rows, aligns }: { head: string[]; rows: string[][]; aligns: string[] }) {
  const al = (k: number) => (aligns[k] === 'center' ? 'text-center' : aligns[k] === 'right' ? 'text-right' : 'text-left')
  return (
    <div className="my-2 overflow-x-auto rounded-lg border border-line">
      <table className="w-full border-collapse text-[13px]">
        <thead className="bg-panel2"><tr>{head.map((h, k) => <th key={k} className={`border-b border-line px-3 py-2 font-semibold ${al(k)}`}>{inline(h)}</th>)}</tr></thead>
        <tbody>{rows.map((r, n) => <tr key={n} className="odd:bg-transparent even:bg-panel2/40">{head.map((_, k) => <td key={k} className={`border-b border-line/60 px-3 py-1.5 align-top ${al(k)}`}>{inline(r[k] ?? '')}</td>)}</tr>)}</tbody>
      </table>
    </div>
  )
}

/** Renderer markdown toi gian (code, in dam, link, danh sach) - khong dung innerHTML nen an toan voi noi dung do model sinh ra. */
export function Markdown({ text }: { text: string }) {
  const blocks = text.split(/```(\w*)\n?([\s\S]*?)(?:```|$)/g)
  const out: ReactNode[] = []
  for (let i = 0; i < blocks.length; i += 3) {
    const prose = blocks[i]
    if (prose.trim()) {
      const lines = prose.replace(/^\n+|\n+$/g, '').split('\n')
      let list: string[] = []
      const flush = (key: string) => {
        if (list.length) out.push(<ul key={key} className="my-1.5 list-disc space-y-0.5 pl-5">{list.map((l, j) => <li key={j}>{inline(l)}</li>)}</ul>)
        list = []
      }
      for (let j = 0; j < lines.length; j++) {
        const line = lines[j]
        if (isRow(line) && j + 1 < lines.length && isSeparator(lines[j + 1])) {  // bang: dong tieu de, dong ngan cach |---|, cac dong du lieu
          flush(`ul${i}-${j}`)
          const head = cells(line)
          const aligns = cells(lines[j + 1]).map((c) => (c.startsWith(':') && c.endsWith(':') ? 'center' : c.endsWith(':') ? 'right' : 'left'))
          const rows: string[][] = []
          j += 2
          while (j < lines.length && isRow(lines[j])) rows.push(cells(lines[j++]))
          j--
          out.push(<Table key={`t${i}-${j}`} head={head} rows={rows} aligns={aligns} />)
          continue
        }
        const li = /^\s*[-*]\s+(.*)$/.exec(line)
        if (li) { list.push(li[1]); continue }
        flush(`ul${i}-${j}`)
        const h = /^#{1,4}\s+(.*)$/.exec(line)
        out.push(h ? <p key={`${i}-${j}`} className="mt-2 font-semibold">{inline(h[1])}</p> : line.trim() ? <p key={`${i}-${j}`}>{inline(line)}</p> : <div key={`${i}-${j}`} className="h-2" />)
      }
      flush(`ul${i}-end`)
    }
    if (i + 2 < blocks.length) out.push(<Code key={`c${i}`} lang={blocks[i + 1]} code={blocks[i + 2].replace(/\n$/, '')} />)
  }
  return <div className="space-y-0.5 break-words">{out}</div>
}
