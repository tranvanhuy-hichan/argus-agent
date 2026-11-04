/** Cung dia chi (bo qua dau / cuoi va hoa thuong). */
export const sameUrl = (a: string, b: string) => a.trim().replace(/\/+$/, '').toLowerCase() === b.trim().replace(/\/+$/, '').toLowerCase()

/** Ten server MCP hop le (a-z, 0-9, - va _) tu mot ten bat ky, khong trung ten da co. */
export function serverName(raw: string, taken: Iterable<string>): string {
  const used = new Set(taken)
  const base = (raw.split('/').pop() ?? raw).toLowerCase().replace(/[^a-z0-9_-]+/g, '-').replace(/^[^a-z0-9]+/, '').slice(0, 26) || 'mcp'
  let n = base, i = 2
  while (used.has(n)) n = `${base}-${i++}`
  return n
}
