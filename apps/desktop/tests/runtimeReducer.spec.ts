import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useRuntimeStore } from '~/stores/runtimeStore'
import { useSessionStore } from '~/stores/sessionStore'

describe('runtime event isolation', () => {
  beforeEach(() => setActivePinia(createPinia()))
  it('merges events by session and run instead of arrival order', async () => {
    const sessions = useSessionStore()
    sessions.upsert({ id: 'a', title: 'A', runs: [], messages: [], tasks: [] })
    sessions.upsert({ id: 'b', title: 'B', runs: [], messages: [], tasks: [] })
    const runtime = useRuntimeStore()
    await runtime.handleEvent({ protocol_version: 1, event_id: '1', type: 'plan.created', occurred_at: '2026-01-01', session_id: 'b', run_id: 'rb', payload: { tasks: [{ id: 'tb', session_id: 'b', run_id: 'rb', description: 'B task', effort: 'high', status: 'queued' }] } })
    await runtime.handleEvent({ protocol_version: 1, event_id: '2', type: 'task.started', occurred_at: '2026-01-01', session_id: 'b', run_id: 'rb', payload: { task_id: 'tb' } })
    expect(sessions.getSession('b')?.tasks[0]?.status).toBe('running')
    expect(sessions.getSession('a')?.tasks).toHaveLength(0)
  })
})
