import { useMemo, useRef } from 'react'
import { highlight, languageFor } from './highlight'

/** Trình soạn thảo gọn: textarea trong suốt đặt trên lớp tô màu cú pháp, có cột số dòng, Tab thụt lề, Ctrl+S để lưu. */
export function CodeEditor({ value, onChange, path, onSave, readOnly }: { value: string; onChange: (v: string) => void; path: string; onSave: () => void; readOnly?: boolean }) {
  const ta = useRef<HTMLTextAreaElement>(null)
  const pre = useRef<HTMLPreElement>(null)
  const gutter = useRef<HTMLDivElement>(null)
  const html = useMemo(() => highlight(value, languageFor(path)) + '\n', [value, path])
  const lines = useMemo(() => value.split('\n').length, [value])

  const sync = () => {
    const el = ta.current
    if (!el) return
    if (pre.current) { pre.current.scrollTop = el.scrollTop; pre.current.scrollLeft = el.scrollLeft }
    if (gutter.current) gutter.current.scrollTop = el.scrollTop
  }
  const onKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); onSave(); return }
    if (e.key === 'Tab' && !readOnly) {
      e.preventDefault()
      const el = e.currentTarget
      const { selectionStart: s, selectionEnd: en } = el
      onChange(value.slice(0, s) + '  ' + value.slice(en))
      requestAnimationFrame(() => { el.selectionStart = el.selectionEnd = s + 2 })
    }
  }
  const font = 'font-mono text-[13px] leading-[20px]'
  return (
    <div className="flex size-full min-h-0 bg-bg">
      <div ref={gutter} aria-hidden className={`${font} w-12 shrink-0 select-none overflow-hidden border-r border-line/60 py-3 pr-2 text-right text-muted/60`}>
        {Array.from({ length: lines }, (_, i) => <div key={i}>{i + 1}</div>)}
      </div>
      <div className="relative min-w-0 flex-1">
        <pre ref={pre} aria-hidden className={`${font} hljs-code pointer-events-none absolute inset-0 m-0 overflow-hidden whitespace-pre p-3`} dangerouslySetInnerHTML={{ __html: html }} />
        <textarea ref={ta} value={value} readOnly={readOnly} onChange={(e) => onChange(e.target.value)} onScroll={sync} onKeyDown={onKey} spellCheck={false} wrap="off" aria-label={path}
          className={`${font} absolute inset-0 size-full resize-none overflow-auto whitespace-pre bg-transparent p-3 text-transparent caret-fg selection:bg-accent/30 focus:outline-none`} />
      </div>
    </div>
  )
}
