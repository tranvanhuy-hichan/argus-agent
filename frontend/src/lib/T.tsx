import { Fragment, type ReactNode } from 'react'
import { t } from './i18n.ts'

/** Dich mot cau co chen phan tu React: <T k="Gửi {code} cho bot" v={{ code: <code>/pair</code> }} /> */
export function T({ k, v }: { k: string; v: Record<string, ReactNode> }) {
  return (
    <>
      {t(k).split(/(\{\w+\})/g).map((part, i) => {
        const m = /^\{(\w+)\}$/.exec(part)
        return m ? <Fragment key={i}>{v[m[1]]}</Fragment> : part
      })}
    </>
  )
}
