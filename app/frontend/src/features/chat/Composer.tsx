import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { ArrowUp, ChevronDown, Mic, Paperclip, Plus, Puzzle, Square, X } from 'lucide-react'
import { t, useLang } from '@/lib/i18n.ts'
import type { Skill } from '@/lib/types'
import { cn } from '@/lib/utils'
import { PermissionMenu } from './PermissionMenu'
import { EFFORTS, type Effort, type Permission } from './permissions'
import { useDictation } from './useDictation'

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
  uploading: boolean
  permission: Permission
  onPermission: (p: Permission) => void
  providers: ProviderOption[]
  provider: string
  onProvider: (id: string) => void
  effort: Effort
  onEffort: (e: Effort) => void
}

/** O chon dang "vien thuoc" (select that, de dung ban phim va trinh doc man hinh). */
function PillSelect({ value, onChange, label, children, disabled, title }: { value: string; onChange: (v: string) => void; label: string; children: React.ReactNode; disabled?: boolean; title?: string }) {
  return (
    <label className={cn('relative flex h-8 items-center rounded-full text-sm text-muted transition hover:bg-panel2 hover:text-fg', disabled && 'opacity-50')} title={title ?? label}>
      <span className="sr-only">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} disabled={disabled} aria-label={label}
        className="h-8 max-w-52 cursor-pointer appearance-none truncate rounded-full bg-transparent pl-3 pr-7 focus:outline-none focus-visible:outline-2 disabled:cursor-not-allowed">{children}</select>
      <ChevronDown className="pointer-events-none absolute right-2 size-3.5" aria-hidden />
    </label>
  )
}

export function Composer(p: Props) {
  const lang = useLang()
  const fileInput = useRef<HTMLInputElement>(null)
  const plusBox = useRef<HTMLDivElement>(null)
  const textarea = useRef<HTMLTextAreaElement>(null)
  const valueRef = useRef(p.value)
  valueRef.current = p.value
  const [hi, setHi] = useState(0)
  const [plusOpen, setPlusOpen] = useState(false)
  const dictation = useDictation(lang, (text) => p.onChange(valueRef.current + (valueRef.current && !/\s$/.test(valueRef.current) ? ' ' : '') + text))

  const slash = p.value.startsWith('/') && !p.value.includes(' ') ? p.value.slice(1).toLowerCase() : null
  const matches = useMemo(() => (slash === null ? [] : p.skills.filter((s) => s.enabled && s.eligible).filter((s) => s.name.toLowerCase().includes(slash)).slice(0, 6)), [slash, p.skills])
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
          <textarea ref={textarea} value={p.value} onChange={(e) => { p.onChange(e.target.value); setHi(0) }} onKeyDown={onKey} rows={1}
            placeholder={t('Nhắn tin cho agent…  (Enter để gửi, Shift+Enter xuống dòng, / để chọn skill)')} aria-label={t('Tin nhắn')}
            className="block max-h-48 min-h-10 w-full resize-none bg-transparent px-2.5 py-2 text-sm placeholder:text-muted/70 focus:outline-none focus-visible:outline-none" style={{ fieldSizing: 'content' } as React.CSSProperties} />

          <div className="mt-1 flex flex-wrap items-center gap-1">
            <input ref={fileInput} type="file" multiple hidden onChange={(e) => { if (e.target.files) p.onAttach([...e.target.files]); e.target.value = '' }} />
            <div ref={plusBox} className="relative">
              <button onClick={() => setPlusOpen(!plusOpen)} aria-haspopup="menu" aria-expanded={plusOpen} aria-label={t('Thêm')} title={t('Thêm')} className="grid size-8 place-items-center rounded-full text-muted transition hover:bg-panel2 hover:text-fg"><Plus className="size-[18px]" /></button>
              {plusOpen && (
                <div role="menu" className="fade-in absolute bottom-full left-0 z-30 mb-2 w-56 rounded-xl border border-line bg-panel p-1.5 shadow-2xl">
                  <button role="menuitem" onClick={() => { setPlusOpen(false); fileInput.current?.click() }} className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm hover:bg-panel2"><Paperclip className="size-4 text-muted" />{t('Đính kèm tệp')}</button>
                  <button role="menuitem" onClick={() => { setPlusOpen(false); p.onChange('/'); textarea.current?.focus() }} className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm hover:bg-panel2"><Puzzle className="size-4 text-muted" />{t('Dùng một skill')}</button>
                </div>
              )}
            </div>
            <PermissionMenu value={p.permission} onChange={p.onPermission} />

            <div className="ml-auto flex items-center gap-0.5">
              <PillSelect value={p.provider} onChange={p.onProvider} label={t('Chọn provider')}>
                {p.providers.map((x) => <option key={x.id} value={x.id}>{x.id} · {x.model}</option>)}
              </PillSelect>
              <PillSelect value={effortOff ? 'auto' : p.effort} onChange={(v) => p.onEffort(v as Effort)} label={t('Mức suy luận')} disabled={effortOff} title={effortOff ? t('Chưa hỗ trợ với provider Anthropic') : t('Mức suy luận')}>
                {EFFORTS.map((e) => <option key={e.id} value={e.id}>{t(e.label)}</option>)}
              </PillSelect>
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
