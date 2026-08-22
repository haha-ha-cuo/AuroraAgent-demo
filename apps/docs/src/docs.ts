// 以仓库根目录 docs/**/*.md 为唯一内容源，构建时以 ?raw 打包进 bundle。
const modules = import.meta.glob('../../../docs/**/*.md', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

function slugFromKey(key: string): string {
  const i = key.indexOf('/docs/')
  const rel = i >= 0 ? key.slice(i + '/docs/'.length) : key
  return rel.replace(/\.md$/, '')
}

export const docsBySlug: Record<string, string> = {}

for (const [key, content] of Object.entries(modules)) {
  docsBySlug[slugFromKey(key)] = content
}

export function getDoc(slug: string): string | undefined {
  return docsBySlug[slug]
}
