<script setup lang="ts">
import { NButton, NEmpty, NIcon, NSpin, useMessage } from 'naive-ui'
import { Folder } from '@vicons/tabler'
import type { AttachmentRef } from '~/types/agent'

const route = useRoute()
const projects = useProjectStore()
const sessions = useSessionStore()
const runtime = useRuntimeStore()
const message = useMessage()
const projectId = computed(() => String(route.params.projectId ?? ''))
const project = computed(() => projects.byId(projectId.value))
const projectSessions = computed(() => sessions.sorted.filter((session) => session.projectId === projectId.value))
const loading = ref(false)
const notFound = ref(false)

async function loadProject(id: string) {
  projects.setActive(id)
  notFound.value = false
  loading.value = true
  try {
    await Promise.all([projects.loadAll(), sessions.loadAll()])
    if (!projects.byId(id)) notFound.value = true
  } catch { notFound.value = true } finally { loading.value = false }
}
watch(projectId, loadProject, { immediate: true })
useHead({ title: computed(() => project.value?.name ?? '项目') })

async function submit(objective: string, attachments: AttachmentRef[]) {
  try {
    const title = objective.replace(/\s+/g, ' ').trim().slice(0, 32)
    const session = await sessions.create(title, projectId.value)
    await navigateTo(`/sessions/${session.id}`)
    await runtime.startRun(session.id, objective, attachments)
  } catch (error) { message.error(error instanceof Error ? error.message : String(error)) }
}
</script>

<template>
  <main class="project-page">
    <div v-if="loading || (!projects.loaded && !notFound)" class="center-state"><NSpin size="large" /></div>
    <template v-else-if="project">
      <section class="project-welcome">
        <span class="project-mark"><NIcon :component="Folder" :size="24" /></span>
        <h1>{{ project.name }}</h1>
        <p>在此项目中发起新对话，或继续下方已有的对话。</p>
      </section>
      <div v-if="projectSessions.length" class="project-sessions">
        <div class="sessions-label">对话（{{ projectSessions.length }}）</div>
        <button v-for="session in projectSessions" :key="session.id" class="session-card" @click="navigateTo(`/sessions/${session.id}`)">
          <span class="session-status" :class="session.status" />
          <span class="session-card-title">{{ session.title }}</span>
          <span class="session-card-meta">{{ session.status }}</span>
        </button>
      </div>
      <div class="project-composer">
        <MessageComposer :disabled="runtime.connectionStatus !== 'connected'" placeholder="在「{{ project.name }}」中描述目标…" @submit="submit" />
      </div>
    </template>
    <div v-else class="center-state"><NEmpty description="没有找到这个项目"><template #extra><NButton @click="navigateTo('/')">返回首页</NButton></template></NEmpty></div>
  </main>
</template>

<style scoped>
.project-page { position: relative; display: grid; width: 100%; height: 100%; grid-template-rows: 1fr auto; padding: 40px 28px 130px; overflow: hidden; }
.center-state { display: grid; height: 100%; place-items: center; }
.project-welcome { max-width: 560px; margin: auto; text-align: center; }
.project-mark { display: grid; width: 52px; height: 52px; margin: 0 auto 18px; place-items: center; border: 1px solid var(--border); border-radius: 15px; background: var(--surface-muted); }
.project-welcome h1 { margin: 0; font-size: clamp(22px, 3vw, 30px); font-weight: 650; letter-spacing: -.03em; }
.project-welcome p { margin: 12px auto 0; color: var(--text-muted); font-size: 13px; }
.project-sessions { width: min(560px, 100%); max-height: 40%; margin: 22px auto 0; overflow: auto; }
.sessions-label { margin-bottom: 8px; color: var(--text-muted); font-size: 11px; font-weight: 650; letter-spacing: .05em; }
.session-card { display: flex; width: 100%; align-items: center; gap: 10px; padding: 11px 13px; border: 1px solid var(--border); border-radius: 10px; background: var(--surface); color: inherit; cursor: pointer; text-align: left; }
.session-card:hover { background: var(--surface-hover); }
.session-status { width: 8px; height: 8px; flex: 0 0 8px; border-radius: 50%; background: #a1a1aa; }
.session-status.running, .session-status.queued { background: #2563eb; }
.session-status.waiting { background: #d69e2e; }
.session-status.completed { background: #22a06b; }
.session-status.failed, .session-status.cancelled { background: #d14343; }
.session-card-title { min-width: 0; flex: 1; overflow: hidden; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.session-card-meta { color: var(--text-muted); font-size: 11px; }
.project-composer { position: absolute; right: 28px; bottom: 28px; left: 28px; width: min(860px, calc(100% - 56px)); margin: auto; }
</style>
