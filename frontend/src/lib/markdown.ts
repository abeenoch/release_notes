// Shared safe markdown → HTML renderer (headings, lists, bold/italic, code, links).
// Extracted from ChangelogDetailPage so the public changelog page renders identically.
export function renderMarkdown(md: string): string {
  // Minimal, safe markdown → HTML (headings, lists, bold/italic, code, links)
  const esc = (s: string) =>
    s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  const escAttr = (s: string) => esc(s).replace(/"/g, '&quot;')
  const safeLink = (text: string, url: string) => {
    const u = url.trim()
    // Allowlist: block javascript:/data:/vbscript: XSS via [x](javascript:...)
    if (!/^(https?:\/\/|mailto:|#|\/)/i.test(u)) {
      return esc(text)
    }
    return `<a href="${escAttr(u)}" target="_blank" rel="noopener">${text}</a>`
  }
  const inline = (s: string) =>
    esc(s)
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/\*([^*]+)\*/g, '<em>$1</em>')
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_m: string, txt: string, url: string) => safeLink(txt, url))

  const lines = md.split('\n')
  const out: string[] = []
  let inList = false
  let inCode = false
  for (const line of lines) {
    if (line.trim().startsWith('```')) {
      if (inCode) { out.push('</code></pre>'); inCode = false }
      else { if (inList) { out.push('</ul>'); inList = false } out.push('<pre><code>'); inCode = true }
      continue
    }
    if (inCode) { out.push(esc(line)); continue }
    const h = /^(#{1,4})\s+(.*)$/.exec(line)
    if (h) {
      if (inList) { out.push('</ul>'); inList = false }
      out.push(`<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`)
      continue
    }
    const li = /^\s*[-*]\s+(.*)$/.exec(line)
    if (li) {
      if (!inList) { out.push('<ul>'); inList = true }
      out.push(`<li>${inline(li[1])}</li>`)
      continue
    }
    if (inList) { out.push('</ul>'); inList = false }
    if (/^\s*$/.test(line)) { out.push(''); continue }
    out.push(`<p>${inline(line)}</p>`)
  }
  if (inList) out.push('</ul>')
  if (inCode) out.push('</code></pre>')
  return out.join('\n')
}
