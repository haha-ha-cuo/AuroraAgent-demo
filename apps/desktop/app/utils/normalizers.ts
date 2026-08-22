import type {
  AttachmentRef,
  ConversationMessage,
  ModelSettings,
  ProjectRecord,
  RunRecord,
  RuntimeInfo,
  SessionRecord,
  TaskNode,
} from '~/types/agent'

type Json = Record<string, any>
const text = (value: unknown, fallback = '') => typeof value === 'string' ? value : fallback
const list = (value: unknown): Json[] => Array.isArray(value) ? value.filter((item): item is Json => !!item && typeof item === 'object') : []

export function normalizeAttachment(raw: Json): AttachmentRef {
  return {
    id: text(raw.id, crypto.randomUUID()),
    name: text(raw.name, text(raw.filename, '附件')),
    path: text(raw.path),
    size: Number(raw.size ?? 0),
    mediaType: text(raw.media_type ?? raw.mime_type ?? raw.mediaType) || null,
  }
}

export function normalizeMessage(raw: Json, sessionId: string): ConversationMessage {
  return {
    id: text(raw.id, crypto.randomUUID()),
    sessionId: text(raw.session_id ?? raw.sessionId, sessionId),
    runId: text(raw.run_id ?? raw.runId) || null,
    role: ['user', 'assistant', 'system', 'tool'].includes(raw.role) ? raw.role : 'system',
    content: text(raw.content),
    createdAt: text(raw.created_at ?? raw.createdAt, new Date().toISOString()),
    status: ['streaming', 'completed', 'failed'].includes(raw.status) ? raw.status : 'completed',
    kind: ['message', 'report', 'error', 'tool'].includes(raw.kind) ? raw.kind : 'message',
    attachments: list(raw.attachments).map(normalizeAttachment),
  }
}

export function normalizeRun(raw: Json, sessionId: string): RunRecord {
  return {
    id: text(raw.id), sessionId: text(raw.session_id ?? raw.sessionId, sessionId),
    objective: text(raw.objective), status: raw.status ?? 'queued', error: text(raw.error),
    createdAt: text(raw.created_at ?? raw.createdAt, new Date().toISOString()),
    updatedAt: text(raw.updated_at ?? raw.updatedAt, new Date().toISOString()),
    retryOfRunId: text(raw.retry_of_run_id ?? raw.retryOfRunId) || null,
    retryTaskId: text(raw.retry_task_id ?? raw.retryTaskId) || null,
  }
}

export function normalizeTask(raw: Json, sessionId: string, runId = ''): TaskNode {
  return {
    id: text(raw.id), sessionId: text(raw.session_id ?? raw.sessionId, sessionId),
    runId: text(raw.run_id ?? raw.runId, runId),
    parentId: text(raw.parent_id ?? raw.parentId) || null,
    description: text(raw.description, '未命名任务'),
    effort: ['low', 'medium', 'high'].includes(raw.effort) ? raw.effort : 'medium',
    status: raw.status ?? 'queued', output: text(raw.output), error: text(raw.error),
    createdAt: text(raw.created_at ?? raw.createdAt), updatedAt: text(raw.updated_at ?? raw.updatedAt),
  }
}

export function normalizeProject(raw: Json): ProjectRecord {
  return {
    id: text(raw.id),
    name: text(raw.name, '未命名项目'),
    createdAt: text(raw.created_at ?? raw.createdAt, new Date().toISOString()),
    updatedAt: text(raw.updated_at ?? raw.updatedAt, new Date().toISOString()),
  }
}

export function normalizeSession(raw: Json): SessionRecord {
  const id = text(raw.id)
  const runs = list(raw.runs).map((item) => normalizeRun(item, id))
  const latestRun = runs.at(-1)?.id ?? ''
  const nestedTasks = list(raw.runs).flatMap((run) => list(run.tasks).map((item) => normalizeTask(item, id, text(run.id))))
  return {
    id,
    title: text(raw.title, '未命名会话'),
    projectId: text(raw.project_id ?? raw.projectId) || null,
    createdAt: text(raw.created_at ?? raw.createdAt, new Date().toISOString()),
    updatedAt: text(raw.updated_at ?? raw.updatedAt, new Date().toISOString()),
    status: raw.status ?? raw.run_status ?? runs.at(-1)?.status ?? 'idle',
    messages: list(raw.messages).map((item) => normalizeMessage(item, id)),
    runs,
    tasks: list(raw.tasks).map((item) => normalizeTask(item, id, latestRun)).concat(nestedTasks),
    approvals: list(raw.approvals).map((item) => ({
      id: text(item.id), sessionId: text(item.session_id, id), runId: text(item.run_id), taskId: text(item.task_id) || null,
      action: text(item.action), risk: text(item.risk), status: item.status ?? 'pending',
    })),
  }
}

export function normalizeRuntime(raw: Json): RuntimeInfo {
  return {
    status: raw.connected === false || raw.status === 'disconnected' ? 'disconnected' : 'connected',
    mode: text(raw.mode, 'mock'), version: text(raw.version, '1'),
    databasePath: text(raw.database_path ?? raw.databasePath ?? raw.database?.path), activeRuns: Number(raw.active_runs ?? raw.activeRuns ?? 0),
  }
}

export function normalizeSettings(raw: Json): ModelSettings {
  return {
    provider: text(raw.provider, 'mock'), baseUrl: text(raw.base_url ?? raw.baseUrl),
    model: text(raw.model, 'mock-agent-v1'), hasApiKey: Boolean(raw.has_api_key ?? raw.api_key_configured ?? raw.hasApiKey),
    mockMode: Boolean(raw.mock_mode ?? raw.mockMode ?? raw.provider === 'mock'),
  }
}
