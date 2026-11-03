import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

const base = 'w-full rounded-lg border border-line bg-bg px-3 text-sm text-fg placeholder:text-muted/70 transition focus:border-accent focus:outline-none'

export function Field({ label, hint, children }: { label: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium text-muted">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-muted/80">{hint}</span>}
    </label>
  )
}

export function Input({ className, ...p }: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...p} className={cn(base, 'h-9', className)} />
}

export function Textarea({ className, ...p }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...p} className={cn(base, 'py-2 font-mono text-[13px] leading-relaxed', className)} />
}

export function Select({ className, ...p }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...p} className={cn(base, 'h-9 pr-8', className)} />
}
