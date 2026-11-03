import { createContext, useContext } from 'react'

/** Phien chat dang mo: de hien anh do agent tao ra ([image: media/x.png]) ngay trong khung chat. */
export const SessionContext = createContext<string | null>(null)
export const useSessionId = () => useContext(SessionContext)

const MARK = /\[image:\s*([^\]\n]+?)\s*\]/g
export const imagePaths = (text: string) => [...text.matchAll(MARK)].map((m) => m[1])
export const stripImageMarks = (text: string) => text.replace(MARK, '').trim()
export const imageUrl = (sid: string, path: string) => `/api/sessions/${sid}/file?path=${encodeURIComponent(path)}&raw=true`
