#!/usr/bin/env node
/**
 * Kiem tra i18n:  node scripts/check-i18n.mjs [tien-to-duong-dan ...]
 *  1. Chuoi tieng Viet nam ngoai t('...') / tk('...') / <T k="..."> (chua duoc boc de dich)
 *  2. Khoa dich co dau tieng Viet nhung thieu ban tieng Anh trong src/i18n/en/*.ts
 *  --english: them danh sach chu TIENG ANH con nam cung trong JSX/thuoc tinh (can doi sang khoa tieng Viet roi dich lai ra tieng Anh)
 *  3. Khoa dung template literal co ${...} (khong dich duoc; dung t('... {bien}', { bien }))
 * Thoat 1 neu co loi.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const root = resolve(import.meta.dirname, '..')
const src = join(root, 'src')
const VI = /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]/i
const args = process.argv.slice(2)
const english = args.includes('--english')
const filters = args.filter((a) => !a.startsWith('--'))

const { EN } = await import(pathToFileURL(join(src, 'i18n/en/index.ts')).href)

// Cung mot khoa khong duoc dich khac nhau o hai file tu dien (dung chung toan cuc)
const seen = {}
for (const f of readdirSync(join(src, 'i18n/en')).filter((f) => f.endsWith('.ts') && f !== 'index.ts')) {
  const dict = (await import(pathToFileURL(join(src, 'i18n/en', f)).href)).default
  for (const [k, v] of Object.entries(dict)) {
    if (k in seen && seen[k].v !== v) console.error(`XUNG DOT khoa ${JSON.stringify(k)}: ${seen[k].f}=${JSON.stringify(seen[k].v)} vs ${f}=${JSON.stringify(v)}`), (process.exitCode = 1)
    seen[k] = { f, v }
  }
}

function walk(dir) {
  return readdirSync(dir).flatMap((f) => {
    const p = join(dir, f)
    return statSync(p).isDirectory() ? (f === 'i18n' ? [] : walk(p)) : /\.(ts|tsx)$/.test(f) ? [p] : []
  })
}

const unescape = (s) => s.replace(/\\(.)/g, (_, c) => (c === 'n' ? '\n' : c))
// t('...') | tk('...') | <T k="..."> voi chuoi nhay don/kep/backtick
const CALL = /(?:\bt|\btk)\(\s*(['"`])((?:\\.|(?!\1)[^\\])*)\1|\bk=(['"])((?:\\.|(?!\3)[^\\])*)\3/g

const problems = []
let keys = 0
for (const file of walk(src)) {
  const rel = relative(root, file)
  if (filters.length && !filters.some((f) => rel.startsWith(f))) continue
  const original = readFileSync(file, 'utf8')
  const blank = (c) => c.replace(/[^\n]/g, ' ')
  // bo comment (giu nguyen vi tri/dong) de vi du trong comment khong bi tinh la khoa hay chuoi chua dich
  const code = original.replace(/\/\*[\s\S]*?\*\//g, blank).split('\n').map((l) => l.replace(/(^|\s)\/\/.*$/, (m, p1) => p1 + blank(m.slice(p1.length)))).join('\n')
  const lines = original.split('\n')
  for (const m of code.matchAll(CALL)) {
    const quote = m[1] ?? m[3]
    const raw = m[2] ?? m[4]
    const line = code.slice(0, m.index).split('\n').length
    if (quote === '`' && raw.includes('${')) { problems.push(`${rel}:${line}: khoa co \${...}, hay dung t('... {bien}', { bien }): ${raw.slice(0, 60)}`); continue }
    const key = unescape(raw)
    keys++
    if (VI.test(key) && !(key in EN)) problems.push(`${rel}:${line}: THIEU ban dich EN: ${JSON.stringify(key)}`)
  }
  // chuoi tieng Viet con sot sau khi go cac loi goi t/tk/T
  if (english) {
    const bare = code.replace(CALL, (all) => blank(all))
    const TEXT = />\s*([^<>{}\n]*[A-Za-z]{3,}[^<>{}\n]*?)\s*</g
    const ATTR = /\b(placeholder|title|aria-label|label|hint|subtitle|alt)="([^"]*[A-Za-z]{3,}[^"]*)"/g
    for (const m of bare.matchAll(TEXT)) if (!/^[\w./:-]+$/.test(m[1].trim()) || /^[A-Z][a-z]+$/.test(m[1].trim())) problems.push(`${rel}:${bare.slice(0, m.index).split('\n').length}: [EN?] van ban JSX: ${m[1].trim().slice(0, 80)}`)
    for (const m of bare.matchAll(ATTR)) problems.push(`${rel}:${bare.slice(0, m.index).split('\n').length}: [EN?] ${m[1]}="${m[2].slice(0, 70)}"`)
  }
  code.replace(CALL, (all) => blank(all)).split('\n').forEach((l, i) => { if (VI.test(l)) problems.push(`${rel}:${i + 1}: chua boc t(): ${lines[i].trim().slice(0, 110)}`) })
}

if (problems.length) {
  console.error(problems.join('\n'))
  console.error(`\n${problems.length} van de (da quet ${keys} khoa dich).`)
  process.exit(1)
}
console.log(`i18n OK: ${keys} khoa dich, ${Object.keys(EN).length} muc tieng Anh.`)
