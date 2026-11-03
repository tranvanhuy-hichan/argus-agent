import { Fragment, useState, type ReactNode } from 'react'
import { Check, Copy } from 'lucide-react'
import { t } from '@/lib/i18n.ts'

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

function inline(text: string): ReactNode[] {
  const re = /(`[^`\n]+`|\*\*[^*\n]+\*\*|\[[^\]\n]+\]\(https?:\/\/[^)\s]+\))/g
  return text.split(re).map((part, i) => {
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
