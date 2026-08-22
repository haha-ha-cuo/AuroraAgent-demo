import { defineStore } from 'pinia'
import type { ApprovalRequest, AttachmentRef, ModelSettings, RuntimeEvent, RuntimeInfo } from '~/types/agent'
import { normalizeMessage, normalizeRun, normalizeRuntime, normalizeSettings, normalizeTask } from '~/utils/normalizers'
import { connectRuntime, onRuntimeEvent, restartRuntimeBroker, runtimeRequest } from '~/utils/runtimeClient'
import { useSessionStore } from '~/stores/sessionStore'
import { useProjectStore } from '~/stores/projectStore'

let initialized: Promise<void> | null = null
let unsubscribe: (() => void) | null = null
const p = (event: RuntimeEvent) => event.payload ?? {}
const value = (record: Record<string, any>, key: string, fallback?: unknown) => record[key] ?? fallback

export const useRuntimeStore = defineStore('runtime', {
  state: () => ({
    connectionStatus: 'disconnected' as RuntimeInfo['status'],
    info: { status: 'disconnected', mode: '', version: '', databasePath: '', activeRuns: 0 } as RuntimeInfo,
    settings: { provider: 'mock', baseUrl: '', model: 'mock-agent-v1', hasApiKey: false, mockMode: true } as ModelSettings,
    approvals: [] as ApprovalRequest[],
    lastError: '',
  }),
  getters: {
    approvalsFor: (state) => (sessionId: string) => state.approvals.filter((item) => item.sessionId === sessionId && item.status === 'pending'),
  },
  actions: {
    restoreApprovals(items: ApprovalRequest[]) {
      for (const item of items) {
        const index = this.approvals.findIndex((approval) => approval.id === item.id)
        if (index >= 0) this.approvals[index] = item
        else this.approvals.push(item)
      }
    },
    async initialize() {
      if (initialized) return initialized
      initialized = (async () => {
        this.connectionStatus = 'connecting'
        try {
          await connectRuntime()
          if (!unsubscribe) unsubscribe = onRuntimeEvent((event) => this.handleEvent(event))
          await this.refreshStatus()
          await Promise.all([useSessionStore().loadAll(), useProjectStore().loadAll(), this.loadSettings()])
          await useSessionStore().importLegacy()
          this.connectionStatus = 'connected'
        } catch (error) {
          this.connectionStatus = 'disconnected'
          this.lastError = error instanceof Error ? error.message : String(error)
          throw error
        }
      })().finally(() => { initialized = null })
      return initialized
    },
    async refreshStatus() {
      const raw = await runtimeRequest<any>('runtime.status')
      this.info = normalizeRuntime(raw?.runtime ?? raw)
      this.connectionStatus = this.info.status
    },
    async restart() {
      this.connectionStatus = 'restarting'
      try {
        await restartRuntimeBroker()
        await this.initialize()
      } catch (error) {
        this.connectionStatus = 'disconnected'
        throw error
      }
    },
    async loadSettings() {
      const raw = await runtimeRequest<any>('settings.get')
      this.settings = normalizeSettings(raw?.settings ?? raw)
    },
    async saveSettings(patch: Partial<ModelSettings> & { apiKey?: string }) {
      const result = await runtimeRequest<any>('settings.update', {
        provider: patch.provider, base_url: patch.baseUrl, model: patch.model,
        api_key: patch.apiKey || undefined,
      })
      this.settings = normalizeSettings(result?.settings ?? result)
    },
    async startRun(sessionId: string, objective: string, attachments: AttachmentRef[] = []) {
      const sessions = useSessionStore()
      const result = await runtimeRequest<any>('run.start', {
        session_id: sessionId,
        objective,
        attachments: attachments.map((item) => ({ id: item.id, name: item.name, path: item.path, size: item.size, media_type: item.mediaType })),
      })
      if (result?.session) sessions.upsert(result.session)
      else await sessions.load(sessionId)
      return result
    },
    async cancelRun(sessionId: string) {
      const session = useSessionStore().sessions.find((item) => item.id === sessionId)
      const run = [...(session?.runs ?? [])].reverse().find((item) => ['queued', 'running', 'waiting'].includes(item.status))
      if (run) await runtimeRequest('run.cancel', { session_id: sessionId, run_id: run.id })
    },
    async retryRun(sessionId: string, runId?: string, taskId?: string) {
      await runtimeRequest('run.retry', { session_id: sessionId, run_id: runId, task_id: taskId })
    },
    async resolveApproval(id: string, approved: boolean) {
      await runtimeRequest('approval.resolve', { request_id: id, approved })
      const request = this.approvals.find((item) => item.id === id)
      if (request) request.status = approved ? 'approved' : 'rejected'
    },
    async handleEvent(event: RuntimeEvent) {
      const sessions = useSessionStore()
      const payload = p(event) as Record<string, any>
      const sessionId = event.session_id ?? String(payload.session_id ?? '')
      const runId = event.run_id ?? String(payload.run_id ?? '')
      const taskId = event.task_id ?? String(payload.task_id ?? payload.id ?? '')
      if (event.type === 'runtime.ready') { this.connectionStatus = 'connected'; await this.refreshStatus().catch(() => {}) }
      if (event.type === 'runtime.disconnected') { this.connectionStatus = 'disconnected'; this.lastError = String(payload.message ?? '运行时已断开') }
      if (event.type === 'project.updated') {
        const projects = useProjectStore()
        const projectId = String(payload.project_id ?? payload.project?.id ?? payload.id ?? '')
        if (payload.deleted) {
          projects.remove(projectId)
          if (projectId) sessions.removeByProject(projectId)
        } else if (payload.project) {
          projects.upsert(payload.project)
        }
      }
      if (!sessionId) return
      let session = sessions.sessions.find((item) => item.id === sessionId)
      if (!session) { await sessions.load(sessionId).catch(() => {}); session = sessions.sessions.find((item) => item.id === sessionId) }
      if (!session) return
      session.updatedAt = event.occurred_at
      if (event.type === 'session.updated' && payload.session) sessions.upsert(payload.session)
      if (event.type === 'session.updated' && payload.deleted) sessions.remove(sessionId)
      if (event.type.startsWith('run.')) {
        const eventStatus = event.type.split('.')[1]
        const status = eventStatus === 'started' ? 'running' : eventStatus
        const raw = payload.run ?? { ...payload, id: runId, session_id: sessionId, status }
        const run = normalizeRun(raw, sessionId)
        const index = session.runs.findIndex((item) => item.id === run.id)
        if (index >= 0) session.runs[index] = { ...session.runs[index], ...run }
        else session.runs.push(run)
        session.status = run.status
        this.info.activeRuns = sessions.sessions.filter((item) => ['queued', 'running', 'waiting'].includes(item.status)).length
      }
      if (event.type === 'plan.created') {
        const tasks = Array.isArray(payload.tasks) ? payload.tasks : []
        for (const raw of tasks) this.mergeTask(session, normalizeTask(raw, sessionId, runId))
      }
      if (event.type.startsWith('task.')) {
        const current = session.tasks.find((item) => item.id === taskId)
        if (payload.task) this.mergeTask(session, normalizeTask(payload.task, sessionId, runId))
        else if (current) {
          if (event.type === 'task.started') current.status = 'running'
          if (event.type === 'task.completed') { current.status = 'completed'; current.output = String(payload.output ?? current.output) }
          if (event.type === 'task.failed') { current.status = 'failed'; current.error = String(payload.error ?? '') }
          if (event.type === 'task.delta') current.output += String(payload.delta ?? payload.text ?? '')
        }
      }
      if (event.type.startsWith('message.')) {
        const status = event.type.split('.')[1] === 'delta' ? 'streaming' : 'completed'
        const raw = payload.message ?? { ...payload, id: payload.message_id ?? payload.id, session_id: sessionId, run_id: runId, status }
        const message = normalizeMessage(raw, sessionId)
        const index = session.messages.findIndex((item) => item.id === message.id)
        if (event.type === 'message.delta' && index >= 0) session.messages[index]!.content += String(payload.delta ?? payload.text ?? '')
        else if (index >= 0) session.messages[index] = { ...session.messages[index], ...message }
        else session.messages.push(message)
      }
      if (event.type === 'approval.requested') {
        this.approvals.push({
          id: String(value(payload, 'request_id', value(payload, 'approval_id', value(payload, 'id', '')))), sessionId, runId,
          taskId: taskId || null, action: String(value(payload, 'action', '执行受保护操作')),
          risk: String(value(payload, 'risk', '需要确认')), details: String(value(payload, 'details', '')),
          status: 'pending',
        })
        session.status = 'waiting'
      }
      if (event.type === 'approval.resolved') {
        const approval = this.approvals.find((item) => item.id === (payload.request_id ?? payload.approval_id ?? payload.id))
        if (approval) approval.status = payload.approved ? 'approved' : 'rejected'
      }
    },
    mergeTask(session: ReturnType<typeof useSessionStore>['sessions'][number], task: ReturnType<typeof normalizeTask>) {
      const index = session.tasks.findIndex((item) => item.id === task.id)
      if (index >= 0) session.tasks[index] = { ...session.tasks[index], ...task }
      else session.tasks.push(task)
      return session.tasks.find((item) => item.id === task.id)!
    },
  },
})
