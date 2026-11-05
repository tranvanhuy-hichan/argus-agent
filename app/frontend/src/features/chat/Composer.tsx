import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { ArrowUp, AtSign, Code2, FileSearch, FileText, Folder, GitBranch, Terminal, Mic, Paperclip, Plus, Puzzle, Square, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import { BrandIcon, type Brand } from '@/components/ui/BrandIcon'
import { t, useLang } from '@/lib/i18n.ts'
import type { Skill } from '@/lib/types'
import { cn } from '@/lib/utils'
import { SLASH_COMMANDS } from './slashCommands'
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
  docs: boolean
  onDocs: (v: boolean) => void
  docsReady: boolean
  project?: string
  onCode?: () => void
  codeExtra?: React.ReactNode
  files?: { path: string; dir: boolean }[]
  onRunCommand?: (text: string) => void
  gitBadge?: { branch: string; changes: number } | null
  skill: string | null
  onSkill: (name: string | null) => void
  temperature?: number
  onTemperature?: (t: number) => void
  maxTokens?: number
  onMaxTokens?: (m: number) => void
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
  const [codeOpen, setCodeOpen] = useState(false)
  const codeBox = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!codeOpen) return
    const down = (e: MouseEvent) => { if (!codeBox.current?.contains(e.target as Node)) setCodeOpen(false) }
    document.addEventListener('mousedown', down)
    return () => document.removeEventListener('mousedown', down)
  }, [codeOpen])
  const dictation = useDictation(lang, (text) => p.onChange(valueRef.current + (valueRef.current && !/\s$/.test(valueRef.current) ? ' ' : '') + text))

  const slash = p.value.startsWith('/') && !p.value.includes(' ') ? p.value.slice(1).toLowerCase() : null
  const matches = useMemo(() => (slash === null ? [] : p.skills.filter((s) => s.enabled && s.eligible).filter((s) => s.name.toLowerCase().includes(slash))), [slash, p.skills])
  const cmds = useMemo(() => (slash === null ? [] : SLASH_COMMANDS.filter((c) => (p.project || !c.code) && c.name.includes(slash))), [slash, p.project])
  type SlashItem = { kind: 'cmd'; name: string; desc: string; needsArg: boolean } | { kind: 'skill'; name: string; desc: string }
  const slashItems: SlashItem[] = [...cmds.map((c) => ({ kind: 'cmd' as const, name: c.name, desc: t(c.desc), needsArg: c.needsArg })), ...matches.map((s) => ({ kind: 'skill' as const, name: s.name, desc: s.description }))]
  const pickSlash = (it: SlashItem) => {
    if (it.kind === 'skill') return pick(it.name)
    setHi(0)
    if (it.needsArg) { p.onChange(`/${it.name} `); setTimeout(() => textarea.current?.focus(), 0) } else { p.onChange(''); p.onRunCommand?.(`/${it.name}`) }
  }
  // Dau @ (dau tu hoac sau khoang trang) -> goi y MCP server/dich vu theo ten
  const at = /(^|\s)@([\w./-]*)$/.exec(p.value.slice(0, caret))
  const atQuery = at ? at[2].toLowerCase() : null
  const atMatches = useMemo(() => (atQuery === null ? [] : p.mentions.filter((m) => m.name.toLowerCase().includes(atQuery)).sort((a, b) => Number(b.status === 'connected') - Number(a.status === 'connected')).slice(0, 8)), [atQuery, p.mentions])
  const atFiles = useMemo(() => {
    if (atQuery === null || !p.files?.length) return []
    const q = atQuery
    const base = (x: string) => x.split('/').pop()!.toLowerCase()
    return p.files.filter((f) => f.path.toLowerCase().includes(q))
      .sort((a, b) => Number(base(b.path).startsWith(q)) - Number(base(a.path).startsWith(q)) || a.path.length - b.path.length).slice(0, 8)
  }, [atQuery, p.files])
  type AtItem = { kind: 'svc'; m: MentionOption } | { kind: 'file'; path: string; dir: boolean }
  const atItems: AtItem[] = [...atMatches.map((m) => ({ kind: 'svc' as const, m })), ...atFiles.map((f) => ({ kind: 'file' as const, path: f.path, dir: f.dir }))]
  const pickAt = (it: AtItem) => (it.kind === 'svc' ? pickMention(it.m.name) : pickMention(it.dir ? `${it.path}/` : it.path, it.dir))
  const pickMention = (name: string, keepOpen = false) => {
    const start = caret - (atQuery?.length ?? 0) - 1
    p.onChange(`${p.value.slice(0, start)}@${name}${keepOpen ? '' : ' '}${p.value.slice(caret)}`)
    const pos = start + name.length + (keepOpen ? 1 : 2)
    setHi(0)
    setTimeout(() => { const el = textarea.current; if (el) { el.focus(); el.setSelectionRange(pos, pos); setCaret(pos) } }, 0)
  }
  const pick = (name: string) => { p.onSkill(name); p.onChange(''); setHi(0); setTimeout(() => textarea.current?.focus(), 0) }
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
    if (atItems.length) {
      if (e.key === 'ArrowDown') { e.preventDefault(); setHi((hi + 1) % atItems.length); return }
      if (e.key === 'ArrowUp') { e.preventDefault(); setHi((hi - 1 + atItems.length) % atItems.length); return }
      if (e.key === 'Tab' || (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing)) { e.preventDefault(); pickAt(atItems[Math.min(hi, atItems.length - 1)]); return }
      if (e.key === 'Escape') { e.preventDefault(); p.onChange(p.value.slice(0, caret - (atQuery?.length ?? 0) - 1) + p.value.slice(caret)); return }
    }
    if (slashItems.length) {
      if (e.key === 'ArrowDown') { e.preventDefault(); setHi((hi + 1) % slashItems.length); return }
      if (e.key === 'ArrowUp') { e.preventDefault(); setHi((hi - 1 + slashItems.length) % slashItems.length); return }
      if (e.key === 'Tab' || (e.key === 'Enter' && !e.shiftKey)) { e.preventDefault(); pickSlash(slashItems[Math.min(hi, slashItems.length - 1)]); return }
    }
    if (e.key === 'Backspace' && !p.value && p.skill) { e.preventDefault(); p.onSkill(null); return }
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); p.onSend() }
  }

  return (
    <div className="shrink-0 bg-bg px-5 pb-4 pt-2">
      <div className="relative mx-auto max-w-4xl">
        {atQuery !== null && (atItems.length > 0 || (p.mentions.length === 0 && !p.files?.length)) && (
          <div className="absolute bottom-full z-20 mb-2 max-h-80 w-full overflow-y-auto rounded-xl border border-line bg-panel shadow-xl" role="listbox" aria-label={t('Tiện ích và tệp')}>
            {atItems.length > 0 ? atItems.map((it, i) => it.kind === 'svc' ? (
              <button key={`s-${it.m.name}`} role="option" aria-selected={i === hi} onMouseEnter={() => setHi(i)} onMouseDown={(e) => e.preventDefault()} onClick={() => pickAt(it)} className={cn('flex w-full items-center gap-3 px-3 py-2 text-left text-sm', i === hi && 'bg-panel2')}>
                <span className="grid size-6 shrink-0 place-items-center rounded-md bg-panel2"><BrandIcon brand={it.m.brand} className="size-4" /></span>
                <span className="font-medium">@{it.m.name}</span>
                <span className={cn('truncate text-xs', it.m.status === 'connected' ? 'text-muted' : 'text-warn')}>{it.m.status === 'connected' ? t('{n} tool', { n: it.m.tools }) : it.m.status === 'needs_auth' ? t('Cần đăng nhập') : t('Chưa kết nối')}</span>
              </button>
            ) : (
              <button key={`f-${it.path}`} role="option" aria-selected={i === hi} onMouseEnter={() => setHi(i)} onMouseDown={(e) => e.preventDefault()} onClick={() => pickAt(it)} className={cn('flex w-full items-center gap-3 px-3 py-1.5 text-left text-sm', i === hi && 'bg-panel2')}>
                {it.dir ? <Folder className="size-4 shrink-0 text-muted" /> : <FileText className="size-4 shrink-0 text-muted" />}
                <span className="shrink-0 font-medium">{it.path.split('/').pop()}{it.dir && '/'}</span><span className="min-w-0 truncate font-mono text-xs text-muted">{it.path.includes('/') ? it.path.slice(0, it.path.lastIndexOf('/')) : ''}</span>
              </button>
            )) : (
              <p className="px-3 py-2.5 text-sm text-muted">{t('Chưa có tiện ích nào.')} <Link to="/plugins" className="text-accent hover:underline">{t('Thêm ở mục Tiện ích')}</Link></p>
            )}
          </div>
        )}
        {slashItems.length > 0 && (
          <div className="absolute bottom-full z-20 mb-2 max-h-72 w-full overflow-y-auto rounded-xl border border-line bg-panel shadow-xl" role="listbox" aria-label={t('Lệnh và kỹ năng')}>
            {slashItems.map((it, i) => (
              <button key={`${it.kind}-${it.name}`} role="option" aria-selected={i === hi} ref={(el) => { if (el && i === hi) el.scrollIntoView({ block: 'nearest' }) }} onMouseEnter={() => setHi(i)} onClick={() => pickSlash(it)} className={cn('flex w-full items-center gap-3 px-3 py-2 text-left text-sm', i === hi && 'bg-panel2')}>
                {it.kind === 'cmd' ? <Terminal className="size-4 shrink-0 text-accent" /> : <Puzzle className="size-4 shrink-0 text-muted" />}
                <span className="shrink-0 whitespace-nowrap font-medium">/{it.name}</span><span className="min-w-0 truncate text-xs text-muted">{it.desc}</span>
              </button>
            ))}
          </div>
        )}
        <div className="rounded-2xl border border-line bg-panel p-2 transition focus-within:border-accent">
          {p.skill && (
            <div className="flex px-1.5 pb-1.5">
              <span className="flex items-center gap-1.5 rounded-md bg-accent/15 py-0.5 pl-2 pr-1 text-xs font-medium text-accent"><Puzzle className="size-3" />{p.skill}
                <button onClick={() => { p.onSkill(null); textarea.current?.focus() }} aria-label={t('Bỏ {name}', { name: p.skill })} className="grid size-4 place-items-center rounded hover:bg-accent/20"><X className="size-3" /></button></span>
            </div>
          )}
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
                  <button role="menuitem" disabled={!p.docsReady} onClick={() => { setPlusOpen(false); p.onDocs(!p.docs) }} title={p.docsReady ? t('Trả lời dựa trên tài liệu bạn đã thêm, có ghi nguồn') : t('Chưa có tài liệu nào. Thêm ở mục Tài liệu.')} className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm hover:bg-panel2 disabled:opacity-40"><FileSearch className="size-4 text-muted" />{t('Hỏi từ tài liệu')}{p.docs && <span className="ml-auto text-xs text-accent">✓</span>}</button>
                  <button role="menuitem" onClick={() => { setPlusOpen(false); p.onChange('/'); textarea.current?.focus() }} className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm hover:bg-panel2"><Puzzle className="size-4 text-muted" />{t('Dùng một skill')}</button>
                </div>
              )}
            </div>

            {p.onCode && (
              <div ref={codeBox} className="relative">
                <button onClick={() => (p.project ? setCodeOpen((o) => !o) : p.onCode?.())} aria-pressed={!!p.project} aria-expanded={codeOpen}
                  title={p.project ? p.project : t('Bật chế độ Lập trình: agent làm việc trực tiếp trong một dự án trên máy')}
                  className={cn('flex h-8 max-w-[20rem] items-center gap-1.5 rounded-full px-3 text-sm transition', p.project ? 'bg-accent/15 text-accent' : 'text-muted hover:bg-panel2 hover:text-fg')}>
                  <Code2 className="size-4 shrink-0" /><span className="truncate">{p.project ? p.project.split('/').filter(Boolean).pop() : t('Lập trình')}</span>
                  {p.project && p.gitBadge && <span className="flex shrink-0 items-center gap-1 font-mono text-[11px] opacity-80"><GitBranch className="size-3" />{p.gitBadge.branch}{p.gitBadge.changes > 0 && <span className="rounded-full bg-accent/20 px-1.5">{p.gitBadge.changes}</span>}</span>}
                </button>
                {codeOpen && p.project && (
                  <div role="dialog" className="fade-in absolute bottom-full left-0 z-30 mb-2 w-[22rem] space-y-3 rounded-xl border border-line bg-panel p-3.5 shadow-2xl">
                    <div className="flex items-center gap-2">
                      <div className="min-w-0 flex-1"><p className="text-xs font-medium">{t('Chế độ Lập trình đang bật')}</p><p className="truncate font-mono text-[11px] text-muted" title={p.project}>{p.project.replace(/^\/home\/[^/]+/, '~')}</p></div>
                      <button onClick={() => { setCodeOpen(false); p.onCode?.() }} className="rounded-md border border-line px-2 py-1 text-xs hover:bg-panel2">{t('Tắt')}</button>
                    </div>
                    {p.codeExtra && <div className="border-t border-line pt-3">{p.codeExtra}</div>}
                  </div>
                )}
              </div>
            )}

            {p.docs && (
              <button onClick={() => p.onDocs(false)} title={t('Đang trả lời từ tài liệu. Bấm để tắt.')} className="flex h-8 items-center gap-1.5 rounded-full bg-accent/15 px-3 text-sm text-accent">
                <FileSearch className="size-4" />{t('Hỏi từ tài liệu')}<X className="size-3" />
              </button>
            )}

            <div className="ml-auto flex items-center gap-0.5">
              <SettingsMenu providers={p.providers} provider={p.provider} onProvider={p.onProvider} effort={p.effort} onEffort={p.onEffort} effortOff={effortOff} permission={p.permission} onPermission={p.onPermission} temperature={p.temperature} onTemperature={p.onTemperature} maxTokens={p.maxTokens} onMaxTokens={p.onMaxTokens} />
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
