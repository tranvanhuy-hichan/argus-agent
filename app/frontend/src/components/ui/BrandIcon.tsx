import type { CSSProperties } from 'react'
import { Bot } from 'lucide-react'
import { siAsana, siAtlassian, siLinear, siNotion } from 'simple-icons'
import canva from '@/assets/brands/canva.svg'
import { cn } from '@/lib/utils'
import antigravity from '@lobehub/icons-static-svg/icons/antigravity-color.svg'
import anthropic from '@lobehub/icons-static-svg/icons/anthropic.svg'
import cerebras from '@lobehub/icons-static-svg/icons/cerebras-color.svg'
import claude from '@lobehub/icons-static-svg/icons/claude-color.svg'
import codex from '@lobehub/icons-static-svg/icons/codex-color.svg'
import deepseek from '@lobehub/icons-static-svg/icons/deepseek-color.svg'
import fireworks from '@lobehub/icons-static-svg/icons/fireworks-color.svg'
import gemini from '@lobehub/icons-static-svg/icons/gemini-color.svg'
import groq from '@lobehub/icons-static-svg/icons/groq.svg'
import lmstudio from '@lobehub/icons-static-svg/icons/lmstudio.svg'
import mistral from '@lobehub/icons-static-svg/icons/mistral-color.svg'
import ollama from '@lobehub/icons-static-svg/icons/ollama.svg'
import openai from '@lobehub/icons-static-svg/icons/openai.svg'
import openrouter from '@lobehub/icons-static-svg/icons/openrouter-color.svg'
import qwen from '@lobehub/icons-static-svg/icons/qwen-color.svg'
import together from '@lobehub/icons-static-svg/icons/together-color.svg'
import vllm from '@lobehub/icons-static-svg/icons/vllm-color.svg'
import xai from '@lobehub/icons-static-svg/icons/xai.svg'

// Logo chinh thuc cua cac hang (bo @lobehub/icons-static-svg). `mono` = logo mot mau, ve theo mau chu cua giao dien (sang/toi).
const BRANDS = {
  // Logo cac dich vu MCP (simple-icons: duong ve nhung san trong goi, khong tai tu mang); Notion mot mau nen ve theo mau chu cua giao dien. Canva khong co trong simple-icons nen dung file SVG rieng.
  notion: { si: siNotion, mono: true }, linear: { si: siLinear }, atlassian: { si: siAtlassian }, asana: { si: siAsana }, canva: { src: canva },
  antigravity: { src: antigravity }, codex: { src: codex }, anthropic: { src: anthropic, mono: true }, cerebras: { src: cerebras }, claude: { src: claude }, deepseek: { src: deepseek }, fireworks: { src: fireworks },
  gemini: { src: gemini }, groq: { src: groq, mono: true }, lmstudio: { src: lmstudio, mono: true }, mistral: { src: mistral }, ollama: { src: ollama, mono: true },
  openai: { src: openai, mono: true }, openrouter: { src: openrouter }, qwen: { src: qwen }, together: { src: together }, vllm: { src: vllm }, xai: { src: xai, mono: true },
} as const
export type Brand = keyof typeof BRANDS

export function BrandIcon({ brand, className }: { brand: Brand | null | undefined; className?: string }) {
  const b = brand ? BRANDS[brand] : null
  if (!b) return <Bot className={cn('size-6 text-muted', className)} aria-hidden />
  if ('si' in b) {
    const mono = 'mono' in b && b.mono === true
    return <svg viewBox="0 0 24 24" aria-hidden className={cn('size-6', mono && 'text-fg', className)}><path d={b.si.path} fill={mono ? 'currentColor' : `#${b.si.hex}`} /></svg>
  }
  if ('mono' in b && b.mono) {
    const style: CSSProperties = { WebkitMaskImage: `url(${JSON.stringify(b.src)})`, maskImage: `url(${JSON.stringify(b.src)})`, WebkitMaskRepeat: 'no-repeat', maskRepeat: 'no-repeat', WebkitMaskPosition: 'center', maskPosition: 'center', WebkitMaskSize: 'contain', maskSize: 'contain', backgroundColor: 'currentColor' }
    return <span aria-hidden className={cn('inline-block size-6 text-fg', className)} style={style} />
  }
  return <img src={b.src} alt="" aria-hidden className={cn('size-6 object-contain', className)} />
}

export function detectBrand(input?: string | { id?: string; name?: string; model?: string; base_url?: string; type?: string; cli?: string } | null): Brand | null {
  if (!input) return null
  if (typeof input === 'object') {
    const { id = '', name = '', model = '', base_url = '', type = '', cli = '' } = input
    if (cli === 'claude') return 'claude'
    if (cli === 'agy') return 'antigravity'
    if (cli === 'codex') return 'codex'
    const combined = `${id} ${name} ${model} ${base_url} ${type}`.toLowerCase()
    return detectBrand(combined)
  }
  const s = input.toLowerCase()
  if (s.includes('ollama') || s.includes('local') || s.includes('11434')) return 'ollama'
  if (s.includes('deepseek')) return 'deepseek'
  if (s.includes('qwen')) return 'qwen'
  if (s.includes('gemini') || s.includes('google') || s.includes('generativelanguage')) return 'gemini'
  if (s.includes('claude') || s.includes('anthropic')) return 'claude'
  if (s.includes('antigravity') || s.includes('agy')) return 'antigravity'
  if (s.includes('openai') || s.includes('gpt') || s.includes('chatgpt')) return 'openai'
  if (s.includes('mistral')) return 'mistral'
  if (s.includes('groq')) return 'groq'
  if (s.includes('openrouter')) return 'openrouter'
  if (s.includes('together')) return 'together'
  if (s.includes('fireworks')) return 'fireworks'
  if (s.includes('cerebras')) return 'cerebras'
  if (s.includes('xai') || s.includes('grok')) return 'xai'
  if (s.includes('lmstudio') || s.includes('1234')) return 'lmstudio'
  if (s.includes('vllm') || s.includes('llama.cpp') || s.includes('8000')) return 'vllm'
  return null
}
