<script setup lang="ts">
import { NButton, NIcon, NSpin, NTag } from 'naive-ui'
import { AlertTriangle, Check, Clock, File, Folder, GitBranch, Loader, Refresh } from '@vicons/tabler'
import type { SessionRecord, TaskNode } from '~/types/agent'

const props = defineProps<{ session: SessionRecord }>()
const runtime = useRuntimeStore()
const requests = computed(() => runtime.approvalsFor(props.session.id))
const activeRun = computed(() => [...props.session.runs].reverse().find((run) => ['queued', 'running', 'waiting'].includes(run.status)))
const failedRun = computed(() => [...props.session.runs].reverse().find((run) => run.status === 'failed'))
const latestRunId = computed(() => props.session.runs.at(-1)?.id)
const visibleTasks = computed(() => props.session.tasks.filter((task) => task.runId === latestRunId.value))
const statusText = computed(() => ({ idle: '就绪', queued: '排队中', running: '正在执行', waiting: '等待确认', completed: '已完成', failed: '执行失败', cancelled: '已取消' }[props.session.status]))
function statusIcon(task: TaskNode) { if (task.status === 'completed') return Check; if (task.status === 'failed') return AlertTriangle; if (task.status === 'running') return Loader; return Clock }
</script>

<template>
  <div class="conversation-view">
    <header class="conversation-header">
      <div class="title-row"><span class="folder-icon"><NIcon :component="Folder" :size="17" /></span><h1>{{ session.title }}</h1></div>
      <div class="header-meta">
        <span class="session-state" :class="session.status">{{ statusText }}</span>
        <NButton v-if="failedRun" quaternary size="small" @click="runtime.retryRun(session.id, failedRun.id)"><template #icon><NIcon :component="Refresh" /></template>重试</NButton>
      </div>
    </header>
    <main class="conversation-scroll app-scrollbar">
      <div class="conversation-column">
        <template v-for="message in session.messages" :key="message.id">
          <div v-if="message.role === 'user'" class="user-block">
            <div class="user-message">{{ message.content }}</div>
            <div v-if="message.attachments.length" class="message-files"><span v-for="file in message.attachments" :key="file.id"><NIcon :component="File" />{{ file.name }}</span></div>
          </div>
          <article v-else-if="message.kind === 'error' || message.status === 'failed'" class="error-message"><NIcon :component="AlertTriangle" :size="18" /><span>{{ message.content }}</span></article>
          <article v-else-if="message.role === 'tool' || message.kind === 'tool'" class="tool-message"><span>工具</span><MarkdownContent :content="message.content" /></article>
          <article v-else class="assistant-message"><MarkdownContent :content="message.content" /><span v-if="message.status === 'streaming'" class="cursor" /></article>
        </template>

        <section v-if="visibleTasks.length" class="execution-section">
          <div class="execution-heading"><span><NIcon :component="GitBranch" :size="16" />最近一次任务执行</span><span>{{ visibleTasks.filter((task) => task.status === 'completed').length }}/{{ visibleTasks.length }}</span></div>
          <article v-for="task in visibleTasks" :key="task.id" :data-task-id="task.id" class="task-card">
            <div class="task-card-head"><NSpin v-if="task.status === 'running'" :size="15" /><NIcon v-else :component="statusIcon(task)" :size="16" :class="['task-icon', task.status]" /><strong>{{ task.description }}</strong><NTag size="small" :bordered="false">{{ task.effort }}</NTag></div>
            <div v-if="task.output || task.error" class="task-output"><MarkdownContent :content="task.output || task.error" /></div>
          </article>
        </section>
        <ApprovalCard v-for="request in requests" :key="request.id" :request="request" @decide="runtime.resolveApproval" />
        <div v-if="activeRun && !session.messages.some((item) => item.status === 'streaming')" class="working-row"><NSpin :size="16" />Agent 正在处理这个会话，你可以切换到其他会话继续工作。</div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.conversation-view{display:grid;width:100%;height:100%;grid-template-rows:56px minmax(0,1fr);overflow:hidden}.conversation-header{display:flex;align-items:center;justify-content:space-between;padding:0 20px;border-bottom:1px solid var(--border);background:var(--surface)}.title-row{display:flex;min-width:0;align-items:center;gap:9px}.folder-icon{display:grid;width:29px;height:29px;place-items:center;border-radius:8px;background:var(--surface-muted);color:var(--text-muted)}.title-row h1{overflow:hidden;margin:0;font-size:14px;font-weight:650;text-overflow:ellipsis;white-space:nowrap}.header-meta{display:flex;align-items:center;gap:7px}.session-state{padding:3px 8px;border-radius:99px;background:var(--surface-muted);color:var(--text-muted);font-size:11px}.session-state.running,.session-state.queued{color:#2563eb}.session-state.waiting{color:#b7791f}.session-state.completed{color:#16845b}.session-state.failed{color:#c33f3f}
.conversation-scroll{overflow:auto;padding:34px 24px 190px}.conversation-column{width:min(820px,100%);margin:0 auto}.user-block{margin:0 0 30px auto;width:fit-content;max-width:78%}.user-message{padding:10px 15px;border-radius:17px;background:var(--surface-muted);font-size:14px;line-height:1.6}.message-files{display:flex;justify-content:flex-end;flex-wrap:wrap;gap:5px;margin-top:6px}.message-files span{display:flex;align-items:center;gap:4px;color:var(--text-muted);font-size:10px}.message-files svg{width:13px}.assistant-message{position:relative;margin:0 0 24px;padding-bottom:20px;border-bottom:1px solid var(--border)}.cursor{display:inline-block;width:6px;height:14px;margin-left:2px;background:var(--text);animation:blink 1s steps(2) infinite}@keyframes blink{50%{opacity:0}}.error-message{display:flex;gap:9px;margin:10px 0 22px;padding:12px;border:1px solid rgb(209 67 67 / 30%);border-radius:9px;background:rgb(209 67 67 / 7%);color:#c33f3f;font-size:13px}.tool-message{margin:8px 0 20px;padding:10px 12px;border-left:2px solid var(--border);background:var(--surface-muted);font-size:12px}.tool-message>span{color:var(--text-muted);font-size:10px;text-transform:uppercase}
.execution-section{margin:4px 0 26px}.execution-heading{display:flex;align-items:center;justify-content:space-between;margin-bottom:9px;color:var(--text-muted);font-size:11px;font-weight:650}.execution-heading span{display:inline-flex;align-items:center;gap:7px}.task-card{margin:6px 0;padding:10px 12px;border:1px solid var(--border);border-radius:9px;background:var(--surface);scroll-margin-top:25px}.task-card-head{display:flex;align-items:center;gap:8px}.task-card-head strong{min-width:0;flex:1;font-size:12px}.task-icon.completed{color:#16845b}.task-icon.failed{color:#c33f3f}.task-output{margin:9px 0 0 24px;padding-top:9px;border-top:1px solid var(--border)}.task-output :deep(.markdown-content){font-size:12px}.working-row{display:flex;align-items:center;gap:9px;color:var(--text-muted);font-size:12px}@media(max-width:680px){.conversation-scroll{padding:26px 16px 176px}.user-block{max-width:92%}}
</style>
