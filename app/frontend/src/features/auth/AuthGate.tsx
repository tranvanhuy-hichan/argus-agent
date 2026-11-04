import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Bot, Lock } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Form'
import { Splash } from '@/components/ui/Splash'
import { api } from '@/lib/api'
import { errMsg } from '@/lib/utils'
import { t } from '@/lib/i18n.ts'

function LoginPage({ onSuccess }: { onSuccess: () => void }) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true); setError('')
    try { await api.post('/api/auth/login', { password }); onSuccess() } catch (err) { setError(errMsg(err)) } finally { setBusy(false) }
  }
  return (
    <div className="grid h-full place-items-center p-4">
      <form onSubmit={(e) => void submit(e)} className="w-full max-w-sm space-y-4 rounded-2xl border border-line bg-panel p-6">
        <div className="flex flex-col items-center gap-2 text-center">
          <div className="grid size-12 place-items-center rounded-xl bg-accent text-accent-fg"><Bot className="size-6" /></div>
          <h1 className="text-lg font-semibold">{t('Đăng nhập Argus Agent')}</h1>
        </div>
        <label className="block"><span className="sr-only">{t('Mật khẩu')}</span>
          <Input type="password" autoFocus autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder={t('Mật khẩu')} /></label>
        {error && <p className="text-sm text-bad" role="alert">{error}</p>}
        <Button variant="primary" type="submit" className="w-full" loading={busy} disabled={!password}><Lock className="size-4" />{t('Đăng nhập')}</Button>
      </form>
    </div>
  )
}

/** Chan toan bo ung dung bang trang dang nhap khi da dat mat khau; bat su kien 401 tu moi lenh goi API. */
const INTRO_MS = 1400
const introSeen = () => { try { return sessionStorage.getItem('argus-intro') === '1' } catch { return false } }

export function AuthGate({ children }: { children: ReactNode }) {
  const qc = useQueryClient()
  const [state, setState] = useState<'loading' | 'ok' | 'login'>('loading')
  // man hinh chao hien it nhat INTRO_MS moi lan mo app (chi mot lan moi tab de khong lam phien khi tai lai trang)
  const [intro, setIntro] = useState(() => !introSeen())
  const [gone, setGone] = useState(() => introSeen())
  useEffect(() => {
    if (!intro) return
    const t1 = setTimeout(() => { setIntro(false); try { sessionStorage.setItem('argus-intro', '1') } catch { /* khong luu duoc thi thoi */ } }, INTRO_MS)
    return () => clearTimeout(t1)
  }, [intro])
  useEffect(() => {  // nut "Xem man hinh chao" o Trang chu
    const replay = () => { setIntro(true); setGone(false) }
    window.addEventListener('argus-intro', replay)
    return () => window.removeEventListener('argus-intro', replay)
  }, [])
  const ready = state !== 'loading' && !intro
  useEffect(() => {
    if (!ready || gone) return
    const t2 = setTimeout(() => setGone(true), 520)
    return () => clearTimeout(t2)
  }, [ready, gone])
  useEffect(() => {
    api.get<{ required: boolean; authenticated: boolean }>('/api/auth/status').then((s) => setState(!s.required || s.authenticated ? 'ok' : 'login')).catch(() => setState('ok'))
    const onAuth = () => setState('login')
    window.addEventListener('auth-required', onAuth)
    return () => window.removeEventListener('auth-required', onAuth)
  }, [])
  const body = state === 'login' ? <LoginPage onSuccess={() => { qc.clear(); setState('ok') }} /> : state === 'ok' ? <>{children}</> : null
  return <>{body}{!gone && <Splash leaving={ready} />}</>
}
