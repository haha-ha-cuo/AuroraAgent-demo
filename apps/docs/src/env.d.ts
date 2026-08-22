/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<Record<string, unknown>, Record<string, unknown>, unknown>
  export default component
}

declare module 'markdown-it-attrs' {
  import type MarkdownIt from 'markdown-it'
  const attrs: (md: MarkdownIt, opts?: Record<string, unknown>) => void
  export default attrs
}
