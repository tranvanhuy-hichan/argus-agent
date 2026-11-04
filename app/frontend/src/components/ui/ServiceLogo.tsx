import { siAirtable, siAsana, siAtlassian, siClickup, siCloudflare, siDatadog, siGithub, siGitlab, siHuggingface, siIntercom, siLinear, siMiro, siNeon, siNetlify, siNotion, siPaypal, siPosthog, siSentry, siSquare, siStripe, siSupabase, siTodoist, siVercel, siWebflow, siWix, siZapier } from 'simple-icons'
import apify from '@/assets/brands/apify.svg'
import canva from '@/assets/brands/canva.svg'
import exa from '@/assets/brands/exa.svg'
import firecrawl from '@/assets/brands/firecrawl.svg'
import microsoft from '@/assets/brands/microsoft.svg'
import monday from '@/assets/brands/monday.svg'
import tavily from '@/assets/brands/tavily.svg'
import { cn } from '@/lib/utils'

type Si = { path: string; hex: string }
// Logo chinh thuc: simple-icons (duong ve nhung trong goi) hoac file SVG rieng; dich vu chua co logo thi hien chu cai dau co mau thuong hieu.
const SI: Record<string, Si> = {
  github: siGithub, gitlab: siGitlab, vercel: siVercel, netlify: siNetlify, 'cloudflare-bindings': siCloudflare, 'cloudflare-observability': siCloudflare, 'cloudflare-docs': siCloudflare,
  sentry: siSentry, datadog: siDatadog, neon: siNeon, supabase: siSupabase, posthog: siPosthog, huggingface: siHuggingface, notion: siNotion, linear: siLinear, asana: siAsana,
  atlassian: siAtlassian, clickup: siClickup, airtable: siAirtable, todoist: siTodoist, miro: siMiro, zapier: siZapier, webflow: siWebflow, wix: siWix, stripe: siStripe,
  paypal: siPaypal, square: siSquare, intercom: siIntercom,
}
const FILE: Record<string, string> = { canva, apify, exa, firecrawl, tavily, monday, 'microsoft-learn': microsoft }

/** Mau qua toi tren nen toi thi ve theo mau chu cua giao dien (GitHub, Vercel, Notion... mot mau den). */
const tooDark = (hex: string) => {
  const n = parseInt(hex, 16)
  return (0.299 * (n >> 16) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255)) < 70
}

export function ServiceLogo({ id, name, color, className }: { id: string; name: string; color: string; className?: string }) {
  const si = SI[id]
  if (si) {
    const mono = tooDark(si.hex)
    return <svg viewBox="0 0 24 24" aria-hidden className={cn('size-5', mono && 'text-fg', className)}><path d={si.path} fill={mono ? 'currentColor' : `#${si.hex}`} /></svg>
  }
  if (FILE[id]) return <img src={FILE[id]} alt="" aria-hidden className={cn('size-5 object-contain', className)} />
  return <span aria-hidden className={cn('grid size-5 place-items-center rounded-md text-[10px] font-bold leading-none text-white', className)} style={{ background: `#${color}` }}>{name.replace(/[^A-Za-z0-9]/g, '').slice(0, 2).toUpperCase()}</span>
}
