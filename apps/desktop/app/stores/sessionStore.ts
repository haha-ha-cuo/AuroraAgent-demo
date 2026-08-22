import { defineStore } from 'pinia'
import type { SessionRecord } from '~/types/agent'
import { normalizeSession } from '~/utils/normalizers'
import { runtimeRequest } from '~/utils/runtimeClient'

const unwrap = (value: any, key: string) => value?.[key] ?? value

export const useSessionStore = defineStore('sessions', {
  state: () => ({
    sessions: [] as SessionRecord[],
    activeSessionId: null as string | null,
    loaded: false,
    loading: false,
  }),
  getters: {
    activeSession: (state) => state.sessions.find((item) => item.id === state.activeSessionId),
    sorted(state): SessionRecord[] {
      return [...state.sessions].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
    },
    isRunning: (state) => (sessionId: string) => state.sessions.some((item) => item.id === sessionId && ['running', 'waiting', 'queued'].includes(item.status)),
  },
  actions: {
    getSession(id: string) { return this.sessions.find((item) => item.id === id) },
    setActive(id: string | null) { this.activeSessionId = id },
    upsert(raw: unknown): SessionRecord {
      const source = raw as Record<string, unknown>
      const session = normalizeSession(source)
      const index = this.sessions.findIndex((item) => item.id === session.id)
      if (index >= 0) {
        const previous = this.sessions[index]!
        if (!Object.hasOwn(source, 'messages')) session.messages = previous.messages
        if (!Object.hasOwn(source, 'runs')) session.runs = previous.runs
        if (!Object.hasOwn(source, 'tasks') && !Array.isArray(source.runs)) session.tasks = previous.tasks
        if (!Object.hasOwn(source, 'approvals')) session.approvals = previous.approvals
        this.sessions[index] = session
      }
      else this.sessions.push(session)
      return session
    },
    remove(id: string) {
      this.sessions = this.sessions.filter((item) => item.id !== id)
      if (this.activeSessionId === id) this.activeSessionId = null
    },
    removeByProject(projectId: string) {
      this.sessions = this.sessions.filter((item) => item.projectId !== projectId)
    },
    async loadAll() {
      if (this.loading) return
      this.loading = true
      try {
        const result = await runtimeRequest<any>('session.list')
        const rows = unwrap(result, 'sessions')
        if (Array.isArray(rows)) {
          const ids = new Set<string>()
          for (const row of rows) { const item = this.upsert(row); ids.add(item.id) }
          this.sessions = this.sessions.filter((item) => ids.has(item.id))
        } else this.sessions = []
        this.loaded = true
      } finally { this.loading = false }
    },
    async load(id: string) {
      const result = await runtimeRequest<any>('session.get', { session_id: id })
      const session = this.upsert(unwrap(result, 'session'))
      useRuntimeStore().restoreApprovals(session.approvals)
      return session
    },
    async create(title = '新对话', projectId?: string | null) {
      const result = await runtimeRequest<any>('session.create', { title, project_id: projectId || undefined })
      const session = this.upsert(unwrap(result, 'session'))
      this.activeSessionId = session.id
      return session
    },
    async rename(id: string, title: string) {
      const result = await runtimeRequest<any>('session.rename', { session_id: id, title })
      return this.upsert(unwrap(result, 'session'))
    },
    async delete(id: string) {
      await runtimeRequest('session.delete', { session_id: id })
      this.remove(id)
    },
    async clearAll() {
      await runtimeRequest('session.clear')
      this.sessions = []
      this.activeSessionId = null
    },
    async importLegacy() {
      if (!import.meta.client) return
      const storageKey = 'demo-agent:sessions:v1'
      const markerKey = 'demo-agent:sqlite-migration:v1'
      if (localStorage.getItem(markerKey)) return
      const raw = localStorage.getItem(storageKey)
      if (!raw) { localStorage.setItem(markerKey, 'empty'); return }
      try {
        const payload = JSON.parse(raw)
        const result = await runtimeRequest<any>('session.import_legacy', {
          import_id: 'local-storage-v1', sessions: Array.isArray(payload?.sessions) ? payload.sessions : [],
        })
        if (result?.failed === 0 || result?.ok === true) {
          localStorage.setItem(markerKey, new Date().toISOString())
          localStorage.removeItem(storageKey)
          await this.loadAll()
        }
      } catch (error) {
        console.warn('[migration] 旧会话暂未迁移，将在下次启动重试', error)
      }
    },
  },
})
