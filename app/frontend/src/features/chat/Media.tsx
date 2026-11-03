import { Volume2, VolumeX } from 'lucide-react'
import { useState } from 'react'
import { t } from '@/lib/i18n.ts'
import { imagePaths, imageUrl, useSessionId } from './session'

export function Images({ text, onOpen }: { text: string; onOpen?: (p: string) => void }) {
  const sid = useSessionId()
  const paths = imagePaths(text)
  if (!sid || !paths.length) return null
  return (
    <div className="my-2 flex flex-wrap gap-2">
      {paths.map((p) => (
        <button key={p} onClick={() => onOpen?.(p)} className="overflow-hidden rounded-lg border border-line bg-panel" title={p}>
          <img src={imageUrl(sid, p)} alt={p} loading="lazy" className="max-h-80 max-w-full object-contain" />
        </button>
      ))}
    </div>
  )
}

const canSpeak = typeof window !== 'undefined' && 'speechSynthesis' in window
const plain = (s: string) => s.replace(/```[\s\S]*?```/g, ' ').replace(/\[image:[^\]]*\]/g, ' ').replace(/[*_`#>]/g, '').replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')

/** Doc to cau tra loi bang giong noi cua trinh duyet (khong ton phi, khong gui du lieu di dau). */
export function SpeakButton({ text }: { text: string }) {
  const [on, setOn] = useState(false)
  if (!canSpeak) return null
  const toggle = () => {
    const s = window.speechSynthesis
    if (on) { s.cancel(); setOn(false); return }
    s.cancel()
    const u = new SpeechSynthesisUtterance(plain(text))
    const lang = /[\u0300-\u036f\u0111]/i.test(text.normalize('NFD')) ? 'vi-VN' : document.documentElement.lang || 'en-US'
    u.lang = lang
    u.onend = u.onerror = () => setOn(false)
    setOn(true)
    s.speak(u)
  }
  const Icon = on ? VolumeX : Volume2
  return <button onClick={toggle} className="flex items-center gap-1 hover:text-fg" aria-pressed={on}><Icon className="size-3" />{on ? t('Dừng đọc') : t('Đọc to')}</button>
}
