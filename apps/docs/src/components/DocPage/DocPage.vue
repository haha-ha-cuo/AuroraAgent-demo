<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NButton, NResult } from 'naive-ui'
import { getDoc } from '../../docs'
import { escapeHtml, renderMarkdown, type RenderedDoc } from '../../markdown'
import { flattenNav, findLabel, pathToSlug, slugToPath } from '../../manifest'
import { SITE } from '../../site'
import { useTheme } from '../../composables/theme'

const route = useRoute()
const router = useRouter()
const { isDark } = useTheme()

const baseUrl = import.meta.env.BASE_URL

const slug = computed(() => {
  const p = route.params.pathMatch
  const joined = Array.isArray(p) ? p.join('/') : (p || '')
  return pathToSlug(joined)
})

const raw = computed(() => getDoc(slug.value))
const notFound = computed(() => raw.value === undefined)

const rendered = computed<RenderedDoc | null>(() => {
  if (raw.value === undefined) return null
  return renderMarkdown(raw.value, slug.value, baseUrl)
})

const contentEl = ref<HTMLElement | null>(null)

watch(
  rendered,
  (r) => {
    document.title = `${r?.title || findLabel(slug.value) || '文档'} · ${SITE.title}`
  },
  { immediate: true },
)

// ---- mermaid ----
async function renderMermaid() {
  const r = rendered.value
  const root = contentEl.value
  if (!r || !root || r.mermaidCodes.size === 0) return
  const { default: mermaid } = await import('mermaid')
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: 'loose',
    theme: isDark.value ? 'dark' : 'neutral',
    fontFamily: 'inherit',
  })
  let seq = 0
  const nodes = root.querySelectorAll<HTMLElement>('.mermaid-block')
  for (const node of nodes) {
    const id = node.getAttribute('data-mmd') || ''
    const code = r.mermaidCodes.get(id)
    if (!code) continue
    node.innerHTML = ''
    try {
      const { svg } = await mermaid.render(
        `mmd-${slug.value.replace(/\W/g, '-')}-${id}-${seq++}-${isDark.value ? 'd' : 'l'}`,
        code,
      )
      node.innerHTML = svg
      node.classList.add('rendered')
    } catch {
      node.innerHTML = `<pre class="mermaid-fallback"><code>${escapeHtml(code)}</code></pre>`
      node.classList.add('rendered', 'error')
    }
  }
}

watch([rendered, isDark], () => nextTick(renderMermaid))

// ---- 锚点滚动 ----
function scrollToHash() {
  if (route.hash) {
    const el = document.getElementById(route.hash.slice(1))
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
      return
    }
  }
  window.scrollTo({ top: 0 })
}

onMounted(() => nextTick(scrollToHash))
watch(() => route.fullPath, () => nextTick(scrollToHash))

// ---- 内容点击拦截：复制按钮 / 站内链接 / 同页锚点 ----
function onContentClick(e: MouseEvent) {
  const target = e.target as HTMLElement

  const copyBtn = target.closest<HTMLButtonElement>('.code-copy')
  if (copyBtn) {
    const idx = copyBtn.getAttribute('data-code-idx') || ''
    const code = rendered.value?.codeStore.get(idx)
    if (code !== undefined) {
      navigator.clipboard?.writeText(code).then(() => {
        const old = copyBtn.textContent
        copyBtn.textContent = '已复制'
        setTimeout(() => (copyBtn.textContent = old), 1200)
      })
    }
    return
  }

  const a = target.closest<HTMLAnchorElement>('a')
  if (!a) return
  const href = a.getAttribute('href') || ''
  if (a.target === '_blank') return
  if (/^https?:\/\//i.test(href) || href.startsWith('//') || href.startsWith('mailto:')) return

  if (href.startsWith('#')) {
    e.preventDefault()
    const el = document.getElementById(href.slice(1))
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    return
  }

  if (href.startsWith(baseUrl) || href.startsWith('/')) {
    e.preventDefault()
    const abs = href.startsWith(baseUrl) ? href.slice(baseUrl.length) : href
    const [path, hash] = abs.split('#')
    const clean = path.replace(/^\/+/, '')
    router.push({ path: '/' + clean, hash: hash ? '#' + hash : undefined })
  }
}

// ---- 上一页 / 下一页 ----
const flat = flattenNav()
const neighbors = computed(() => {
  const i = flat.findIndex((x) => x.slug === slug.value)
  return {
    prev: i > 0 ? flat[i - 1] : null,
    next: i >= 0 && i < flat.length - 1 ? flat[i + 1] : null,
  }
})

const editUrl = computed(() => {
  const file = slug.value
  return `${SITE.repo}/edit/main/docs/${file}.md`
})

// ---- 本页目录（仅 h2/h3）+ 滚动高亮 ----
const toc = computed(() =>
  (rendered.value?.headings ?? []).filter((h) => h.level === 2 || h.level === 3),
)

const activeHeading = ref('')
let observer: IntersectionObserver | null = null

function setupScrollSpy() {
  observer?.disconnect()
  activeHeading.value = ''
  if (!contentEl.value) return
  const ids = toc.value.map((h) => h.id)
  if (!ids.length) return
  observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) activeHeading.value = entry.target.id
      }
    },
    { rootMargin: '-72px 0px -70% 0px', threshold: 0 },
  )
  for (const id of ids) {
    const el = document.getElementById(id)
    if (el) observer.observe(el)
  }
}

watch([rendered, toc], () => nextTick(setupScrollSpy))
onBeforeUnmount(() => observer?.disconnect())

function scrollToHeading(id: string) {
  const el = document.getElementById(id)
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
</script>

<template>
  <div ref="contentEl" class="doc-page" @click="onContentClick">
    <div v-if="notFound" class="not-found">
      <n-result
        status="404"
        title="页面不存在"
        :description="`没有找到路径 /${slug === 'index' ? '' : slug} 对应的文档`"
      >
        <template #footer>
          <n-button type="primary" @click="router.push('/')">返回首页</n-button>
        </template>
      </n-result>
    </div>

    <template v-else-if="rendered">
      <div class="doc-grid">
        <article class="markdown-body" v-html="rendered.html"></article>

        <aside v-if="toc.length" class="doc-toc">
          <div class="toc-title">本页目录</div>
          <nav class="toc-list">
            <a
              v-for="h in toc"
              :key="h.id"
              :href="'#' + h.id"
              :class="['toc-item', 'toc-l' + h.level, { active: activeHeading === h.id }]"
              @click.prevent="scrollToHeading(h.id)"
              >{{ h.text }}</a
            >
          </nav>
        </aside>
      </div>

      <footer class="doc-footer">
        <div class="doc-meta">
          <a class="edit-link" :href="editUrl" target="_blank" rel="noopener noreferrer"
            >在 GitHub 上编辑此页</a
          >
        </div>
        <div class="doc-nav">
          <n-button
            v-if="neighbors.prev"
            quaternary
            size="small"
            @click="router.push(slugToPath(neighbors.prev.slug))"
          >
            ← {{ neighbors.prev.label }}
          </n-button>
          <span v-else></span>
          <n-button
            v-if="neighbors.next"
            quaternary
            size="small"
            type="primary"
            @click="router.push(slugToPath(neighbors.next.slug))"
          >
            {{ neighbors.next.label }} →
          </n-button>
        </div>
      </footer>
    </template>
  </div>
</template>
