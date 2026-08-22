import MarkdownIt, { type Token } from 'markdown-it'
import attrs from 'markdown-it-attrs'
import hljs from 'highlight.js/lib/core'
import bash from 'highlight.js/lib/languages/bash'
import python from 'highlight.js/lib/languages/python'
import plaintext from 'highlight.js/lib/languages/plaintext'
import javascript from 'highlight.js/lib/languages/javascript'
import typescript from 'highlight.js/lib/languages/typescript'
import json from 'highlight.js/lib/languages/json'
import yaml from 'highlight.js/lib/languages/yaml'

hljs.registerLanguage('bash', bash)
hljs.registerLanguage('shell', bash)
hljs.registerLanguage('sh', bash)
hljs.registerLanguage('python', python)
hljs.registerLanguage('py', python)
hljs.registerLanguage('plaintext', plaintext)
hljs.registerLanguage('text', plaintext)
hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('json', json)
hljs.registerLanguage('yaml', yaml)

export interface Heading {
  id: string
  text: string
  level: number
}

export interface RenderedDoc {
  html: string
  title: string
  headings: Heading[]
  mermaidCodes: Map<string, string>
  codeStore: Map<string, string>
}

export function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function slugify(s: string): string {
  const slug = s
    .trim()
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s\-_]/gu, '')
    .replace(/\s+/g, '-')
    .replace(/-{2,}/g, '-')
    .replace(/^[-_]+|[-_]+$/g, '')
  return slug || 'section'
}

function inlineText(token: Token): string {
  let out = ''
  const walk = (t: Token) => {
    if (t.type === 'text' || t.type === 'code_inline') out += t.content || ''
    if (t.children) for (const c of t.children) walk(c)
  }
  walk(token)
  return out.trim()
}

// 把 `## 标题 {: #custom-id }` 规范化为 markdown-it-attrs 的 `{#custom-id}` 形式，
// 保证 ADR 等章节的自定义锚点稳定可用。
function normalizeHeadingAttrs(src: string): string {
  return src.replace(/^(\s*#{1,6}\s+.*?)\s*\{:\s*([^}]*)\}\s*$/gm, (_m, head, body) => {
    const cleaned = body.trim().replace(/\s+/g, ' ')
    return cleaned ? `${head} {${cleaned}}` : head
  })
}

function resolveSlug(currentSlug: string, target: string): string {
  const dir = currentSlug.includes('/') ? currentSlug.slice(0, currentSlug.lastIndexOf('/')) : ''
  const parts = dir ? dir.split('/').filter(Boolean) : []
  for (const seg of target.split('/')) {
    if (seg === '.' || seg === '') continue
    if (seg === '..') {
      parts.pop()
      continue
    }
    parts.push(seg)
  }
  return parts.join('/')
}

export function renderMarkdown(src: string, currentSlug: string, baseUrl: string): RenderedDoc {
  const headings: Heading[] = []
  const mermaidCodes = new Map<string, string>()
  const codeStore = new Map<string, string>()

  const md = new MarkdownIt({
    html: true,
    linkify: true,
    breaks: false,
  })

  md.use(attrs)

  // 收集标题、为缺失的标题补 id（供锚点与「本页目录」使用）
  md.core.ruler.push('collect_headings', (state) => {
    const used = new Set<string>()
    for (let i = 0; i < state.tokens.length; i++) {
      const t = state.tokens[i]
      if (t.type !== 'heading_open') continue
      const level = Number(t.tag.slice(1))
      const inline = state.tokens[i + 1]
      const text = inlineText(inline)
      let id = t.attrGet('id') || slugify(text)
      let uid = id
      let n = 2
      while (used.has(uid)) uid = `${id}-${n++}`
      used.add(uid)
      t.attrSet('id', uid)
      headings.push({ id: uid, text, level })
    }
    return true
  })

  // 代码块：mermaid 交给专用组件渲染，其余走 highlight.js
  let mermaidSeq = 0
  let codeSeq = 0
  const defaultFence =
    md.renderer.rules.fence ||
    ((tokens, idx, opts, _env, self) => self.renderToken(tokens, idx, opts))
  md.renderer.rules.fence = (tokens, idx, opts, env, self) => {
    const token = tokens[idx]
    const lang = (token.info || '').trim().split(/\s+/)[0].toLowerCase()
    const code = token.content
    if (lang === 'mermaid') {
      const id = String(mermaidSeq++)
      mermaidCodes.set(id, code)
      return `<div class="mermaid-block" data-mmd="${id}"></div>`
    }
    const idx2 = String(codeSeq++)
    codeStore.set(idx2, code)
    const realLang = lang && hljs.getLanguage(lang) ? lang : 'plaintext'
    const highlighted = hljs.highlight(code, { language: realLang }).value
    return (
      `<div class="code-block" data-lang="${escapeHtml(lang || 'text')}">` +
      `<button class="code-copy" type="button" data-code-idx="${idx2}" title="复制代码">复制</button>` +
      `<pre><code class="hljs">${highlighted}</code></pre></div>`
    )
  }

  // 站内链接重写：相对 .md → 路由路径；外链新窗口打开
  const defaultLinkOpen =
    md.renderer.rules.link_open ||
    ((tokens, idx, opts, _env, self) => self.renderToken(tokens, idx, opts))
  md.renderer.rules.link_open = (tokens, idx, opts, env, self) => {
    const token = tokens[idx]
    const href = token.attrGet('href') || ''

    if (/^https?:\/\//i.test(href) || href.startsWith('//') || href.startsWith('mailto:')) {
      token.attrSet('target', '_blank')
      token.attrSet('rel', 'noopener noreferrer')
    } else if (href.startsWith('#')) {
      // 同页锚点，交给点击拦截器平滑滚动
    } else {
      const [pathPart, fragment] = href.split('#')
      if (pathPart.endsWith('.md')) {
        const resolved = resolveSlug(currentSlug, pathPart).replace(/\.md$/, '')
        const url =
          baseUrl +
          (resolved === 'index' ? '' : resolved) +
          (fragment ? '#' + fragment : '')
        token.attrSet('href', url)
      }
    }
    return defaultLinkOpen(tokens, idx, opts, env, self)
  }

  const html = md.render(normalizeHeadingAttrs(src))
  const title = headings.length ? headings[0].text : ''

  return { html, title, headings, mermaidCodes, codeStore }
}
