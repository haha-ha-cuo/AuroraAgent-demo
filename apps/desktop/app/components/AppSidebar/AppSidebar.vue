<script setup lang="ts">
import { NButton, NDropdown, NIcon, NInput, NScrollbar, NTooltip, useDialog, useMessage } from 'naive-ui'
import { Dots, MessagePlus, Messages, Robot, Search, Settings } from '@vicons/tabler'
import type { SessionRecord, TaskNode } from '~/types/agent'

const route = useRoute()
const sessions = useSessionStore()
const dialog = useDialog()
const message = useMessage()
const detailTask = ref<TaskNode | null>(null)
const currentSession = computed(() => sessions.getSession?.(String(route.params.sessionId ?? '')) ?? sessions.sessions.find((s) => s.id === route.params.sessionId))
const currentTasks = computed(() => {
  const session = currentSession.value
  const runId = session?.runs.at(-1)?.id
  return runId ? session!.tasks.filter((task) => task.runId === runId) : []
})

const groups = computed(() => {
  const today = new Date(); today.setHours(0, 0, 0, 0)
  const week = new Date(today); week.setDate(week.getDate() - 7)
  const result = [{ label: '今天', items: [] as SessionRecord[] }, { label: '过去 7 天', items: [] as SessionRecord[] }, { label: '更早', items: [] as SessionRecord[] }]
  for (const session of sessions.recentSessions) {
    const date = new Date(session.updatedAt)
    result[date >= today ? 0 : date >= week ? 1 : 2]!.items.push(session)
  }
  return result.filter((group) => group.items.length)
})

function menuOptions(session: SessionRecord) {
  return [
    { label: '重命名', key: `rename:${session.id}` },
    { label: '删除', key: `delete:${session.id}` },
  ]
}

async function handleMenu(key: string, session: SessionRecord) {
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
  <aside class="sidebar">
    <div class="brand-row">
      <span class="brand-mark"><NIcon :component="Robot" :size="19" /></span>
      <strong class="brand-name">Demo Agent</strong>
      <RuntimeStatus class="runtime" />
    </div>
    <nav class="primary-nav" aria-label="主导航">
      <NTooltip placement="right"><template #trigger>
        <NButton quaternary class="nav-button" :class="{ active: route.path === '/' }" @click="navigateTo('/')"><template #icon><NIcon :component="MessagePlus" /></template><span class="nav-label">新对话</span></NButton>
      </template>新对话</NTooltip>
      <NTooltip placement="right"><template #trigger>
        <NButton quaternary class="nav-button" :class="{ active: route.path === '/settings' }" @click="navigateTo('/settings')"><template #icon><NIcon :component="Settings" /></template><span class="nav-label">设置</span></NButton>
      </template>设置</NTooltip>
    </nav>

    <section class="recent-section">
      <div class="section-label"><NIcon :component="Messages" :size="14" /><span>会话</span></div>
      <NInput v-model:value="sessions.query" size="small" clearable placeholder="搜索会话" class="session-search"><template #prefix><NIcon :component="Search" /></template></NInput>
      <NScrollbar class="recent-scroll">
        <template v-if="groups.length">
          <div v-for="group in groups" :key="group.label" class="time-group">
            <span class="time-label">{{ group.label }}</span>
            <button v-for="session in group.items" :key="session.id" class="session-link" :class="{ active: route.params.sessionId === session.id }" @click="navigateTo(`/sessions/${session.id}`)">
              <span class="session-status" :class="session.status" />
              <span class="session-title">{{ session.title }}</span>
              <NDropdown trigger="click" :options="menuOptions(session)" @select="(key) => handleMenu(String(key), session)">
                <span class="session-menu" role="button" aria-label="会话操作" @click.stop><NIcon :component="Dots" :size="16" /></span>
              </NDropdown>
            </button>
          </div>
        </template>
        <p v-else class="empty-recent">{{ sessions.query ? '没有匹配的会话' : '暂无会话' }}</p>
      </NScrollbar>
    </section>

    <TaskTreePanel :tasks="currentTasks" @select="detailTask = $event" />
    <TaskDetailsDrawer v-model:show="detailTask" />
  </aside>
</template>

<style scoped>
.sidebar { display:flex; width:100%; height:100%; flex-direction:column; background:transparent; overflow:hidden; }
.brand-row { display:flex; min-height:56px; align-items:center; gap:9px; padding:0 13px; }
.brand-mark { display:grid; width:28px; height:28px; flex:0 0 28px; place-items:center; border:1px solid var(--border); border-radius:8px; background:var(--surface); }
.brand-name { min-width:0; flex:1; font-size:14px; white-space:nowrap; }.runtime{flex:0 0 auto}
.primary-nav{display:grid;gap:2px;padding:3px 8px 8px}.nav-button{width:100%;height:34px;justify-content:flex-start;color:var(--text)}.nav-button.active{background:var(--surface-hover)}
.recent-section{display:flex;min-height:170px;max-height:42%;flex-direction:column;padding-bottom:7px}.section-label{display:flex;align-items:center;gap:7px;padding:7px 14px;color:var(--text-muted);font-size:11px;font-weight:650;letter-spacing:.05em}
.session-search{width:calc(100% - 16px);margin:0 8px 7px}.session-search :deep(.n-input){background:var(--surface)}.recent-scroll{min-height:0;flex:1}.time-group{display:grid;gap:1px;padding:0 8px 7px}.time-label{padding:5px 7px 3px;color:var(--text-muted);font-size:10px}
.session-link{display:flex;width:100%;min-width:0;align-items:center;gap:8px;padding:7px;border:0;border-radius:7px;background:transparent;color:inherit;cursor:pointer;text-align:left}.session-link:hover,.session-link.active{background:var(--surface-hover)}
.session-status{width:7px;height:7px;flex:0 0 7px;border-radius:50%;background:#a1a1aa}.session-status.running,.session-status.queued{background:#2563eb}.session-status.waiting{background:#d69e2e}.session-status.completed{background:#22a06b}.session-status.failed,.session-status.cancelled{background:#d14343}
.session-title{min-width:0;flex:1;overflow:hidden;font-size:12px;text-overflow:ellipsis;white-space:nowrap}.session-menu{display:grid;width:22px;height:22px;place-items:center;border-radius:5px;color:var(--text-muted);opacity:0}.session-link:hover .session-menu,.session-link.active .session-menu{opacity:1}.empty-recent{margin:10px 15px;color:var(--text-muted);font-size:12px}
@media(max-width:860px){.sidebar{align-items:center}.brand-row{width:100%;justify-content:center;padding:0}.brand-name,.nav-label,.recent-section,.runtime{display:none}.primary-nav{width:100%;padding:6px 8px 10px}.nav-button{justify-content:center;padding:0}}
</style>
