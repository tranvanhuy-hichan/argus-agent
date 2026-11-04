import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { ArrowUp, AtSign, Mic, Paperclip, Plus, Puzzle, Square, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import { BrandIcon, type Brand } from '@/components/ui/BrandIcon'
import { t, useLang } from '@/lib/i18n.ts'
import type { Skill } from '@/lib/types'
import { cn } from '@/lib/utils'
import { SettingsMenu } from './SettingsMenu'
import type { Effort, Permission } from './permissions'
import { useDictation } from './useDictation'

/** MCP server/dich vu goi duoc bang dau @ trong tin nhan. */
export interface MentionOption { name: string; brand: Brand | null; status: 'connecting' | 'connected' | 'error' | 'disabled' | 'needs_auth'; tools: number }
export interface ProviderOption { id: string; model: string; type: 'openai' | 'anthropic' | 'cli' }

interface Props {
  value: string
  onChange: (v: string) => void
  onSend: () => void
  onStop: () => void
  busy: boolean
  attachments: string[]
  onAttach: (files: File[]) => void
  onRemoveAttachment: (path: string) => void
  skills: Skill[]
  mentions: MentionOption[]
  uploading: boolean
  permission: Permission
  onPermission: (p: Permission) => void
  providers: ProviderOption[]
  provider: string
  onProvider: (id: string) => void
  effort: Effort
  onEffort: (e: Effort) => void
}

export function Composer(p: Props) {
  const lang = useLang()
  const fileInput = useRef<HTMLInputElement>(null)
  const plusBox = useRef<HTMLDivElement>(null)
  const textarea = useRef<HTMLTextAreaElement>(null)
  const valueRef = useRef(p.value)
  valueRef.current = p.value
  const [hi, setHi] = useState(0)
  const [caret, setCaret] = useState(0)
  const [plusOpen, setPlusOpen] = useState(false)
  const dictation = useDictation(lang, (text) => p.onChange(valueRef.current + (valueRef.current && !/\s$/.test(valueRef.current) ? ' ' : '') + text))

  const slash = p.value.startsWith('/') && !p.value.includes(' ') ? p.value.slice(1).toLowerCase() : null
  const matches = useMemo(() => (slash === null ? [] : p.skills.filter((s) => s.enabled && s.eligible).filter((s) => s.name.toLowerCase().includes(slash)).slice(0, 6)), [slash, p.skills])
  // Dau @ (dau tu hoac sau khoang trang) -> goi y MCP server/dich vu theo ten
  const at = /(^|\s)@([\w-]*)$/.exec(p.value.slice(0, caret))
  const atQuery = at ? at[2].toLowerCase() : null
  const atMatches = useMemo(() => (atQuery === null ? [] : p.mentions.filter((m) => m.name.toLowerCase().includes(atQuery)).sort((a, b) => Number(b.status === 'connected') - Number(a.status === 'connected')).slice(0, 8)), [atQuery, p.mentions])
  const pickMention = (name: string) => {
    const start = caret - (atQuery?.length ?? 0) - 1
    p.onChange(`${p.value.slice(0, start)}@${name} ${p.value.slice(caret)}`)
    const pos = start + name.length + 2
    setHi(0)
    setTimeout(() => { const el = textarea.current; if (el) { el.focus(); el.setSelectionRange(pos, pos); setCaret(pos) } }, 0)
  }
  const pick = (name: string) => { p.onChange(t('Dùng skill `{name}`: ', { name })); setHi(0); textarea.current?.focus() }
  const current = p.providers.find((x) => x.id === p.provider)
  const effortOff = current?.type === 'anthropic' || current?.type === 'cli'

  useEffect(() => {
    if (!plusOpen) return
    const down = (e: MouseEvent) => { if (!plusBox.current?.contains(e.target as Node)) setPlusOpen(false) }
    const key = (e: globalThis.KeyboardEvent) => { if (e.key === 'Escape') setPlusOpen(false) }
    document.addEventListener('mousedown', down)
    document.addEventListener('keydown', key)
    return () => { document.removeEventListener('mousedown', down); document.removeEventListener('keydown', key) }
  }, [plusOpen])

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (atMatches.length) {
      if (e.key === 'ArrowDown') { e.preventDefault(); setHi((hi + 1) % atMatches.length); return }
      if (e.key === 'ArrowUp') { e.preventDefault(); setHi((hi - 1 + atMatches.length) % atMatches.length); return }
      if (e.key === 'Tab' || (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing)) { e.preventDefault(); pickMention(atMatches[hi].name); return }
      if (e.key === 'Escape') { e.preventDefault(); p.onChange(p.value.slice(0, caret - (atQuery?.length ?? 0) - 1) + p.value.slice(caret)); return }
    }
    if (matches.length) {
      if (e.key === 'ArrowDown') { e.preventDefault(); setHi((hi + 1) % matches.length); return }
      if (e.key === 'ArrowUp') { e.preventDefault(); setHi((hi - 1 + matches.length) % matches.length); return }
      if (e.key === 'Tab' || (e.key === 'Enter' && !e.shiftKey)) { e.preventDefault(); pick(matches[hi].name); return }
    }
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); p.onSend() }
  }

  return (
    <div className="shrink-0 bg-bg px-5 pb-4 pt-2">
      <div className="relative mx-auto max-w-4xl">
        {atQuery !== null && (atMatches.length > 0 || p.mentions.length === 0) && (
          <div className="absolute bottom-full z-20 mb-2 w-full overflow-hidden rounded-xl border border-line bg-panel shadow-xl" role="listbox" aria-label={t('Dịch vụ MCP')}>
            {atMatches.length > 0 ? atMatches.map((m, i) => (
              <button key={m.name} role="option" aria-selected={i === hi} onMouseEnter={() => setHi(i)} onMouseDown={(e) => e.preventDefault()} onClick={() => pickMention(m.name)} className={cn('flex w-full items-center gap-3 px-3 py-2 text-left text-sm', i === hi && 'bg-panel2')}>
                <span className="grid size-6 shrink-0 place-items-center rounded-md bg-panel2"><BrandIcon brand={m.brand} className="size-4" /></span>
                <span className="font-medium">@{m.name}</span>
                <span className={cn('truncate text-xs', m.status === 'connected' ? 'text-muted' : 'text-warn')}>{m.status === 'connected' ? t('{n} tool', { n: m.tools }) : m.status === 'needs_auth' ? t('Cần đăng nhập') : t('Chưa kết nối')}</span>
              </button>
            )) : (
              <p className="px-3 py-2.5 text-sm text-muted">{t('Chưa có dịch vụ MCP nào.')} <Link to="/integrations?tab=services" className="text-accent hover:underline">{t('Thêm ở Kết nối → MCP dịch vụ')}</Link></p>
            )}
          </div>
        )}
        {matches.length > 0 && (
          <div className="absolute bottom-full z-20 mb-2 w-full overflow-hidden rounded-xl border border-line bg-panel shadow-xl" role="listbox" aria-label={t('Kỹ năng')}>
            {matches.map((s, i) => (
              <button key={s.name} role="option" aria-selected={i === hi} onMouseEnter={() => setHi(i)} onClick={() => pick(s.name)} className={cn('flex w-full items-center gap-3 px-3 py-2 text-left text-sm', i === hi && 'bg-panel2')}>
                <Puzzle className="size-4 shrink-0 text-muted" /><span className="font-medium">/{s.name}</span><span className="truncate text-xs text-muted">{s.description}</span>
              </button>
            ))}
          </div>
        )}
        <div className="rounded-2xl border border-line bg-panel p-2 transition focus-within:border-accent">
          {(p.attachments.length > 0 || p.uploading) && (
            <div className="flex flex-wrap gap-1.5 px-1.5 pb-2">
              {p.attachments.map((a) => (
                <span key={a} className="flex items-center gap-1 rounded-md border border-line bg-bg px-2 py-0.5 text-xs"><Paperclip className="size-3 text-muted" />{a.split('/').pop()}
                  <button onClick={() => p.onRemoveAttachment(a)} aria-label={t('Bỏ {name}', { name: a })} className="text-muted hover:text-fg"><X className="size-3" /></button></span>
              ))}
              {p.uploading && <span className="text-xs text-muted">{t('Đang tải lên…')}</span>}
            </div>
          )}
          <textarea ref={textarea} value={p.value} onChange={(e) => { p.onChange(e.target.value); setCaret(e.target.selectionStart); setHi(0) }} onKeyDown={onKey} onKeyUp={(e) => setCaret(e.currentTarget.selectionStart)} onClick={(e) => setCaret(e.currentTarget.selectionStart)} rows={1}
            placeholder={t('Nhắn tin cho agent…  (Enter để gửi, Shift+Enter xuống dòng, / để chọn skill, @ để gọi dịch vụ)')} aria-label={t('Tin nhắn')}
            className="block max-h-48 min-h-10 w-full resize-none bg-transparent px-2.5 py-2 text-sm placeholder:text-muted/70 focus:outline-none focus-visible:outline-none" style={{ fieldSizing: 'content' } as React.CSSProperties} />

          <div className="mt-1 flex flex-wrap items-center gap-1">
            <input ref={fileInput} type="file" multiple hidden onChange={(e) => { if (e.target.files) p.onAttach([...e.target.files]); e.target.value = '' }} />
            <div ref={plusBox} className="relative">
              <button onClick={() => setPlusOpen(!plusOpen)} aria-haspopup="menu" aria-expanded={plusOpen} aria-label={t('Thêm')} title={t('Thêm')} className="grid size-8 place-items-center rounded-full text-muted transition hover:bg-panel2 hover:text-fg"><Plus className="size-[18px]" /></button>
              {plusOpen && (
                <div role="menu" className="fade-in absolute bottom-full left-0 z-30 mb-2 w-56 rounded-xl border border-line bg-panel p-1.5 shadow-2xl">
                  <button role="menuitem" onClick={() => { setPlusOpen(false); fileInput.current?.click() }} className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm hover:bg-panel2"><Paperclip className="size-4 text-muted" />{t('Đính kèm tệp')}</button>
                  <button role="menuitem" onClick={() => { setPlusOpen(false); const v = p.value; const sep = v && !/\s$/.test(v) ? ' ' : ''; p.onChange(`${v}${sep}@`); setTimeout(() => { const el = textarea.current; if (el) { el.focus(); setCaret(el.value.length) } }, 0) }} className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm hover:bg-panel2"><AtSign className="size-4 text-muted" />{t('Gọi một dịch vụ (@)')}</button>
                  <button role="menuitem" onClick={() => { setPlusOpen(false); p.onChange('/'); textarea.current?.focus() }} className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm hover:bg-panel2"><Puzzle className="size-4 text-muted" />{t('Dùng một skill')}</button>
                </div>
              )}
            </div>

            <div className="ml-auto flex items-center gap-0.5">
              <SettingsMenu providers={p.providers} provider={p.provider} onProvider={p.onProvider} effort={p.effort} onEffort={p.onEffort} effortOff={effortOff} permission={p.permission} onPermission={p.onPermission} />
              {dictation.supported && (
                <button onClick={dictation.toggle} aria-pressed={dictation.listening} aria-label={dictation.listening ? t('Dừng ghi âm') : t('Nói để nhập')} title={dictation.listening ? t('Dừng ghi âm') : t('Nói để nhập')}
                  className={cn('grid size-8 place-items-center rounded-full transition', dictation.listening ? 'animate-pulse bg-bad/15 text-bad' : 'text-muted hover:bg-panel2 hover:text-fg')}><Mic className="size-4" /></button>
              )}
              {p.busy ? (
                <button onClick={p.onStop} aria-label={t('Dừng')} className="ml-1 grid size-9 place-items-center rounded-full bg-panel2 transition hover:bg-line"><Square className="size-3.5 fill-current" /></button>
              ) : (
                <button onClick={p.onSend} disabled={!p.value.trim() || p.uploading} aria-label={t('Gửi')} className="ml-1 grid size-9 place-items-center rounded-full bg-accent text-accent-fg transition hover:brightness-110 disabled:opacity-40"><ArrowUp className="size-4" /></button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
