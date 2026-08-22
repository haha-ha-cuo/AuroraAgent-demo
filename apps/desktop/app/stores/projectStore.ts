import { defineStore } from 'pinia'
import type { ProjectRecord } from '~/types/agent'
import { normalizeProject } from '~/utils/normalizers'
import { runtimeRequest } from '~/utils/runtimeClient'
import { useSessionStore } from '~/stores/sessionStore'

const unwrap = (value: any, key: string) => value?.[key] ?? value

export const useProjectStore = defineStore('projects', {
  state: () => ({
    projects: [] as ProjectRecord[],
    activeProjectId: null as string | null,
    loaded: false,
    loading: false,
  }),
  getters: {
    activeProject: (state) => state.projects.find((item) => item.id === state.activeProjectId),
    byId: (state) => (id: string) => state.projects.find((item) => item.id === id),
  },
  actions: {
    setActive(id: string | null) { this.activeProjectId = id },
    upsert(raw: unknown): ProjectRecord {
      const project = normalizeProject(raw as Record<string, unknown>)
      const index = this.projects.findIndex((item) => item.id === project.id)
      if (index >= 0) this.projects[index] = project
      else this.projects.push(project)
      return project
    },
    remove(id: string) {
      this.projects = this.projects.filter((item) => item.id !== id)
      if (this.activeProjectId === id) this.activeProjectId = null
    },
    async loadAll() {
      if (this.loading) return
      this.loading = true
      try {
        const result = await runtimeRequest<any>('project.list')
        const rows = unwrap(result, 'projects')
        if (Array.isArray(rows)) {
          const ids = new Set<string>()
          for (const row of rows) { const item = this.upsert(row); ids.add(item.id) }
          this.projects = this.projects.filter((item) => ids.has(item.id))
        } else this.projects = []
        this.loaded = true
      } finally { this.loading = false }
    },
    async get(id: string) {
      const result = await runtimeRequest<any>('project.get', { project_id: id })
      const project = this.upsert(result)
      const rows = result?.sessions
      if (Array.isArray(rows)) {
        const sessionStore = useSessionStore()
        for (const row of rows) sessionStore.upsert(row)
      }
      return project
    },
    async create(name = '新项目') {
      const result = await runtimeRequest<any>('project.create', { name })
      const project = this.upsert(unwrap(result, 'project'))
      this.activeProjectId = project.id
      return project
    },
    async rename(id: string, name: string) {
      const result = await runtimeRequest<any>('project.rename', { project_id: id, name })
      return this.upsert(unwrap(result, 'project'))
    },
    async delete(id: string) {
      await runtimeRequest('project.delete', { project_id: id })
      this.remove(id)
      useSessionStore().removeByProject(id)
    },
  },
})
