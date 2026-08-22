<script setup lang="ts">
import { NButton, NDropdown, NIcon, NScrollbar, NTooltip, useDialog, useMessage } from 'naive-ui'
import { ChevronDown, ChevronLeft, ChevronRight, Dots, Folder, FolderPlus, Messages, Robot, Settings } from '@vicons/tabler'
import type { ProjectRecord, SessionRecord, TaskNode } from '~/types/agent'

const props = defineProps<{ collapsed?: boolean }>()
const route = useRoute()
const sessions = useSessionStore()
const projects = useProjectStore()
const ui = useUiStore()
const dialog = useDialog()
const message = useMessage()
const detailTask = ref<TaskNode | null>(null)
const expandedProjects = ref<Record<string, boolean>>({})

const currentSession = computed(() => sessions.getSession?.(String(route.params.sessionId ?? '')) ?? sessions.sessions.find((s) => s.id === route.params.sessionId))
const currentTasks = computed(() => {
  const session = currentSession.value
  const runId = session?.runs.at(-1)?.id
  return runId ? session!.tasks.filter((task) => task.runId === runId) : []
})

const projectGroups = computed(() => {
  const fallbackId = projects.projects[0]?.id
  const groups = new Map<string, { project: ProjectRecord; sessions: SessionRecord[] }>()
  for (const project of projects.projects) groups.set(project.id, { project, sessions: [] })
  for (const session of sessions.sorted) {
    const target = groups.get(session.projectId ?? '') ?? (fallbackId ? groups.get(fallbackId) : undefined)
    target?.sessions.push(session)
  }
  return [...groups.values()]
})

function isExpanded(id: string) { return expandedProjects.value[id] ?? true }
function toggleProject(id: string) { expandedProjects.value[id] = !isExpanded(id) }
function toggleCollapse() { ui.sidebarCollapsed = !ui.sidebarCollapsed }

function projectMenuOptions(project: ProjectRecord) {
  return [
    { label: '新建对话', key: `new:${project.id}` },
    { label: '重命名', key: `rename:${project.id}` },
    { label: '删除项目', key: `delete:${project.id}` },
  ]
}

function sessionMenuOptions(session: SessionRecord) {
  return [
    { label: '重命名', key: `rename:${session.id}` },
    { label: '删除', key: `delete:${session.id}` },
  ]
}

async function createProject() {
  const name = window.prompt('输入新项目名称')?.trim()
  if (!name) return
  try {
    const project = await projects.create(name)
    await navigateTo(`/projects/${project.id}`)
  } catch (error) { message.error(String(error)) }
}

async function createSession(projectId: string) {
  try {
    const session = await sessions.create('新对话', projectId)
    await navigateTo(`/sessions/${session.id}`)
  } catch (error) { message.error(String(error)) }
}

async function handleProjectMenu(key: string, project: ProjectRecord) {
  if (key.startsWith('new:')) { await createSession(project.id); return }
  if (key.startsWith('rename:')) {
    const name = window.prompt('输入新的项目名称', project.name)?.trim()
    if (name && name !== project.name) await projects.rename(project.id, name).catch((error) => message.error(String(error)))
    return
  }
  dialog.warning({
    title: '删除项目？',
    content: `项目「${project.name}」及其所有对话将永久删除。`,
    positiveText: '删除', negativeText: '取消',
    onPositiveClick: async () => {
      await projects.delete(project.id)
      if (route.params.projectId === project.id) await navigateTo('/')
      message.success('项目已删除')
    },
  })
}

async function handleSessionMenu(key: string, session: SessionRecord) {
  if (key.startsWith('rename:')) {
    const title = window.prompt('输入新的会话标题', session.title)?.trim()
    if (title && title !== session.title) await sessions.rename(session.id, title).catch((error) => message.error(String(error)))
    return
  }
  dialog.warning({
    title: '删除会话？', content: `“${session.title}”及其消息、运行和任务将永久删除。`,
    positiveText: '删除', negativeText: '取消',
    onPositiveClick: async () => {
      await sessions.delete(session.id)
      if (route.params.sessionId === session.id) await navigateTo('/')
      message.success('会话已删除')
    },
  })
}
</script>

<template>
  <aside class="sidebar" :class="{ collapsed }">
    <div class="brand-row">
      <span class="brand-mark"><NIcon :component="Robot" :size="19" /></span>
      <strong v-if="!collapsed" class="brand-name">Demo Agent</strong>
      <RuntimeStatus v-if="!collapsed" class="runtime" />
      <NButton quaternary circle size="tiny" class="collapse-button" :aria-label="collapsed ? '展开菜单' : '收起菜单'" @click="toggleCollapse">
        <template #icon><NIcon :component="collapsed ? ChevronRight : ChevronLeft" /></template>
      </NButton>
    </div>

    <nav class="primary-nav" aria-label="主导航">
      <NTooltip placement="right" :disabled="!collapsed"><template #trigger>
        <NButton quaternary class="nav-button" @click="createProject"><template #icon><NIcon :component="FolderPlus" /></template><span v-if="!collapsed" class="nav-label">新项目</span></NButton>
      </template>新项目</NTooltip>
      <NTooltip placement="right" :disabled="!collapsed"><template #trigger>
        <NButton quaternary class="nav-button" :class="{ active: route.path === '/settings' }" @click="navigateTo('/settings')"><template #icon><NIcon :component="Settings" /></template><span v-if="!collapsed" class="nav-label">设置</span></NButton>
      </template>设置</NTooltip>
    </nav>

    <section class="projects-section">
      <div v-if="!collapsed" class="section-label"><NIcon :component="Messages" :size="14" /><span>项目</span></div>
      <NScrollbar class="projects-scroll">
        <div v-for="group in projectGroups" :key="group.project.id" class="project-group">
          <div class="project-header" :class="{ active: route.params.projectId === group.project.id }">
            <button class="project-toggle" :aria-label="isExpanded(group.project.id) ? '折叠项目' : '展开项目'" @click="toggleProject(group.project.id)">
              <NIcon :component="isExpanded(group.project.id) ? ChevronDown : ChevronRight" :size="13" />
            </button>
            <button class="project-name" @click="navigateTo(`/projects/${group.project.id}`)">
              <NIcon :component="Folder" :size="15" />
              <span v-if="!collapsed" class="project-label">{{ group.project.name }}</span>
            </button>
            <NDropdown v-if="!collapsed" trigger="click" :options="projectMenuOptions(group.project)" @select="(key) => handleProjectMenu(String(key), group.project)">
              <span class="project-menu" role="button" aria-label="项目操作" @click.stop><NIcon :component="Dots" :size="15" /></span>
            </NDropdown>
          </div>
          <template v-if="isExpanded(group.project.id)">
            <div v-if="group.sessions.length" class="project-sessions">
              <button v-for="session in group.sessions" :key="session.id" class="session-link" :class="{ active: route.params.sessionId === session.id }" @click="navigateTo(`/sessions/${session.id}`)">
                <span class="session-status" :class="session.status" />
                <span v-if="!collapsed" class="session-title">{{ session.title }}</span>
                <NDropdown v-if="!collapsed" trigger="click" :options="sessionMenuOptions(session)" @select="(key) => handleSessionMenu(String(key), session)">
                  <span class="session-menu" role="button" aria-label="会话操作" @click.stop><NIcon :component="Dots" :size="14" /></span>
                </NDropdown>
              </button>
            </div>
            <p v-else-if="!collapsed" class="empty-project">暂无对话</p>
          </template>
        </div>
      </NScrollbar>
    </section>

    <TaskTreePanel v-if="!collapsed" :tasks="currentTasks" @select="detailTask = $event" />
    <TaskDetailsDrawer v-model:show="detailTask" />
  </aside>
</template>

<style scoped>
.sidebar { display: flex; width: 100%; height: 100%; flex-direction: column; background: transparent; overflow: hidden; }
.brand-row { display: flex; min-height: 56px; align-items: center; gap: 9px; padding: 0 13px; }
.brand-mark { display: grid; width: 28px; height: 28px; flex: 0 0 28px; place-items: center; border: 1px solid var(--border); border-radius: 8px; background: var(--surface); }
.brand-name { min-width: 0; flex: 1; font-size: 14px; white-space: nowrap; }
.runtime { flex: 0 0 auto; }
.collapse-button { flex: 0 0 auto; color: var(--text-muted); }

.primary-nav { display: grid; gap: 2px; padding: 3px 8px 8px; }
.nav-button { width: 100%; height: 34px; justify-content: flex-start; color: var(--text); }
.nav-button.active { background: var(--surface-hover); }

.projects-section { display: flex; min-height: 180px; flex: 1; flex-direction: column; padding-bottom: 7px; }
.section-label { display: flex; align-items: center; gap: 7px; padding: 7px 14px; color: var(--text-muted); font-size: 11px; font-weight: 650; letter-spacing: .05em; }
.projects-scroll { min-height: 0; flex: 1; }
.project-group { display: grid; gap: 1px; padding: 0 8px 7px; }
.project-header { display: flex; align-items: center; gap: 2px; padding: 2px 4px; border-radius: 7px; color: var(--text); }
.project-header:hover, .project-header.active { background: var(--surface-hover); }
.project-toggle { display: grid; width: 20px; height: 26px; place-items: center; padding: 0; border: 0; background: transparent; color: var(--text-muted); cursor: pointer; }
.project-name { display: flex; min-width: 0; flex: 1; align-items: center; gap: 8px; padding: 5px 0; border: 0; background: transparent; color: inherit; cursor: pointer; text-align: left; }
.project-name svg { color: var(--text-muted); }
.project-label { min-width: 0; flex: 1; overflow: hidden; font-size: 12.5px; font-weight: 620; text-overflow: ellipsis; white-space: nowrap; }
.project-menu { display: grid; width: 22px; height: 22px; place-items: center; border-radius: 5px; color: var(--text-muted); opacity: 0; }
.project-header:hover .project-menu { opacity: 1; }
.project-sessions { display: grid; gap: 1px; padding: 2px 0 2px 22px; }
.empty-project { margin: 6px 0 2px 22px; color: var(--text-muted); font-size: 11px; }

.session-link { display: flex; width: 100%; min-width: 0; align-items: center; gap: 8px; padding: 7px; border: 0; border-radius: 7px; background: transparent; color: inherit; cursor: pointer; text-align: left; }
.session-link:hover, .session-link.active { background: var(--surface-hover); }
.session-status { width: 7px; height: 7px; flex: 0 0 7px; border-radius: 50%; background: #a1a1aa; }
.session-status.running, .session-status.queued { background: #2563eb; }
.session-status.waiting { background: #d69e2e; }
.session-status.completed { background: #22a06b; }
.session-status.failed, .session-status.cancelled { background: #d14343; }
.session-title { min-width: 0; flex: 1; overflow: hidden; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.session-menu { display: grid; width: 22px; height: 22px; place-items: center; border-radius: 5px; color: var(--text-muted); opacity: 0; }
.session-link:hover .session-menu, .session-link.active .session-menu { opacity: 1; }

.collapsed .brand-row { justify-content: center; padding: 0; }
.collapsed .collapse-button { position: absolute; }
.collapsed .primary-nav { padding: 6px 8px 10px; }
.collapsed .nav-button { justify-content: center; padding: 0; }
.collapsed .projects-section { min-height: 0; }
.collapsed .project-toggle { display: none; }
.collapsed .project-name { justify-content: center; }
.collapsed .project-sessions { padding-left: 0; }
.collapsed .session-link { justify-content: center; padding: 8px; }
.collapsed .session-status { flex-basis: 7px; }
</style>
