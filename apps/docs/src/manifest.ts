// 站点导航清单：与 docs/ 目录一一对应（Markdown 单一内容源）。
// slug 相对 docs/ 目录，不含 .md 后缀；首页用 'index'。
export interface NavLeaf {
  label: string
  slug: string
}

export interface NavGroup {
  label: string
  children: NavLeaf[]
}

export type NavItem = NavLeaf | NavGroup

export const NAV: NavItem[] = [
  { label: '首页', slug: 'index' },
  {
    label: '快速开始',
    children: [
      { label: '环境准备', slug: 'getting-started/prerequisites' },
      { label: '文档本地预览', slug: 'getting-started/docs-preview' },
      { label: '运行最小 demo', slug: 'getting-started/demo' },
    ],
  },
  {
    label: '项目概览',
    children: [
      { label: '项目简介', slug: 'overview/introduction' },
      { label: '设计目标', slug: 'overview/goals' },
      { label: '技术栈', slug: 'overview/tech-stack' },
    ],
  },
  {
    label: '架构设计',
    children: [
      { label: '总体架构', slug: 'architecture/overview' },
      { label: 'Python 模块职责', slug: 'architecture/python-modules' },
      { label: '桌面应用架构', slug: 'architecture/desktop' },
      { label: '任务委派树', slug: 'architecture/delegation-tree' },
      { label: '推理强度', slug: 'architecture/reasoning-effort' },
      { label: '能力特化层', slug: 'architecture/capability-layer' },
      { label: '模型接入与 API 管理', slug: 'architecture/model-access' },
      { label: 'MCP 集成', slug: 'architecture/mcp' },
      { label: '评估与校准 (eval)', slug: 'architecture/eval' },
      { label: '关键决策 (ADR)', slug: 'architecture/decisions' },
    ],
  },
  { label: '路线图', slug: 'roadmap' },
  { label: '贡献指南', slug: 'contributing' },
]

export function slugToPath(slug: string): string {
  return slug === 'index' ? '/' : '/' + slug
}

export function pathToSlug(path: string): string {
  const p = path.replace(/^\/+|\/+$/g, '')
  return p === '' ? 'index' : p
}

export function flattenNav(): Array<{ label: string; slug: string }> {
  const out: Array<{ label: string; slug: string }> = []
  for (const item of NAV) {
    if ('children' in item) out.push(...item.children)
    else out.push(item)
  }
  return out
}

export function findLabel(slug: string): string | undefined {
  return flattenNav().find((x) => x.slug === slug)?.label
}
