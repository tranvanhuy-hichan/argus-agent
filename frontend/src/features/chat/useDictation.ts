import { useCallback, useEffect, useRef, useState } from 'react'

interface Recognition {
  lang: string
  continuous: boolean
  interimResults: boolean
  onresult: ((e: { resultIndex: number; results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }> }) => void) | null
  onend: (() => void) | null
  onerror: (() => void) | null
  start: () => void
  stop: () => void
}
type RecognitionCtor = new () => Recognition

const Ctor = (typeof window !== 'undefined' ? ((window as unknown as Record<string, unknown>).SpeechRecognition ?? (window as unknown as Record<string, unknown>).webkitSpeechRecognition) : undefined) as RecognitionCtor | undefined

/** Nhap bang giong noi qua Web Speech API cua trinh duyet (Chrome/Edge/Safari); an nut neu khong ho tro. */
export function useDictation(lang: 'vi' | 'en', onText: (text: string) => void) {
  const [listening, setListening] = useState(false)
  const rec = useRef<Recognition | null>(null)
  const cb = useRef(onText)
  cb.current = onText

  useEffect(() => () => rec.current?.stop(), [])

  const toggle = useCallback(() => {
    if (!Ctor) return
    if (rec.current && listening) { rec.current.stop(); return }
    const r = new Ctor()
    r.lang = lang === 'vi' ? 'vi-VN' : 'en-US'
    r.continuous = true
    r.interimResults = false
    r.onresult = (e) => {
      let text = ''
      for (let i = e.resultIndex; i < e.results.length; i++) if (e.results[i].isFinal) text += e.results[i][0].transcript
      if (text.trim()) cb.current(text.trim())
    }
    r.onend = () => setListening(false)
    r.onerror = () => setListening(false)
    rec.current = r
    r.start()
    setListening(true)
  }, [lang, listening])

  return { supported: !!Ctor, listening, toggle }
}
