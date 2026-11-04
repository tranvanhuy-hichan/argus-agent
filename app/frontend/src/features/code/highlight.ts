import hljs from 'highlight.js/lib/core'
import bash from 'highlight.js/lib/languages/bash'
import c from 'highlight.js/lib/languages/c'
import cpp from 'highlight.js/lib/languages/cpp'
import css from 'highlight.js/lib/languages/css'
import go from 'highlight.js/lib/languages/go'
import java from 'highlight.js/lib/languages/java'
import javascript from 'highlight.js/lib/languages/javascript'
import json from 'highlight.js/lib/languages/json'
import markdown from 'highlight.js/lib/languages/markdown'
import php from 'highlight.js/lib/languages/php'
import python from 'highlight.js/lib/languages/python'
import rust from 'highlight.js/lib/languages/rust'
import sql from 'highlight.js/lib/languages/sql'
import typescript from 'highlight.js/lib/languages/typescript'
import xml from 'highlight.js/lib/languages/xml'
import yaml from 'highlight.js/lib/languages/yaml'

const LANGS = { bash, c, cpp, css, go, java, javascript, json, markdown, php, python, rust, sql, typescript, xml, yaml }
for (const [name, def] of Object.entries(LANGS)) hljs.registerLanguage(name, def)

const BY_EXT: Record<string, string> = {
  py: 'python', js: 'javascript', jsx: 'javascript', mjs: 'javascript', cjs: 'javascript', ts: 'typescript', tsx: 'typescript', json: 'json',
  css: 'css', scss: 'css', html: 'xml', htm: 'xml', xml: 'xml', svg: 'xml', vue: 'xml', sh: 'bash', bash: 'bash', zsh: 'bash', md: 'markdown',
  yml: 'yaml', yaml: 'yaml', toml: 'yaml', sql: 'sql', go: 'go', rs: 'rust', java: 'java', c: 'c', h: 'c', cpp: 'cpp', cc: 'cpp', hpp: 'cpp', php: 'php',
}

export const languageFor = (path: string): string | null => BY_EXT[path.split('.').pop()?.toLowerCase() ?? ''] ?? null

const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

/** HTML đã tô màu cú pháp; file quá lớn hoặc không nhận ra ngôn ngữ thì chỉ escape. */
export function highlight(code: string, lang: string | null): string {
  if (!lang || code.length > 250_000) return esc(code)
  try { return hljs.highlight(code, { language: lang, ignoreIllegals: true }).value } catch { return esc(code) }
}
