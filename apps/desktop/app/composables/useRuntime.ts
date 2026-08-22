// Agent 运行时客户端。
//
// 传输抽象（二选一，同一套事件协议）：
// - 打包态（Tauri）：经 stdio 中继 —— invoke('agent_run'/'agent_confirm') 下发，
//   Rust 把 sidecar stdout 上的事件转成 `agent-event` 事件回推。
// - 开发态（浏览器）：直连 `--port` 的 WebSocket 服务。
//
// 事件协议见 demo_agent/server.py 顶部注释。
import { ref } from 'vue'
import { useIpc } from './useIpc'

export interface AgentEvent {
  type: string
  [key: string]: unknown
}

export interface Task {
  id: string
  description: string
  effort: 'low' | 'medium' | 'high'
}

export interface ConfirmRequest {
  requestId: string
  action: string
  risk: string
}

export function useRuntime() {
  const { call, on, inTauri } = useIpc()

  const status = ref<'disconnected' | 'connecting' | 'connected'>('disconnected')
  const events = ref<AgentEvent[]>([])
  const tasks = ref<Task[]>([])
  const report = ref('')
  const confirmRequests = ref<ConfirmRequest[]>([])

  const devWsUrl = 'ws://127.0.0.1:8765/ws'
  let ws: WebSocket | null = null
  const unlisteners: Array<() => void> = []

  function push(ev: AgentEvent) {
    events.value.push(ev)
    if (ev.type === 'plan') tasks.value = (ev.tasks as Task[]) ?? []
    if (ev.type === 'report') report.value = String(ev.report ?? '')
    if (ev.type === 'confirm_request') {
      confirmRequests.value.push({
        requestId: String(ev.request_id),
        action: String(ev.action),
        risk: String(ev.risk),
      })
    }
  }

  function reset() {
    events.value = []
    tasks.value = []
    report.value = ''
    confirmRequests.value = []
  }

  async function connect() {
    if (inTauri) {
      unlisteners.push(
        await on<AgentEvent>('agent-event', (ev) => {
          if (ev.type === 'hello') status.value = 'connected'
          push(ev)
        }),
        await on<string>('agent-stderr', (line) => console.warn('[agent]', line)),
        await on<string>('agent-error', (msg) => {
          status.value = 'disconnected'
          console.error('[agent]', msg)
        }),
        await on<unknown>('agent-exit', () => {
          status.value = 'disconnected'
        }),
      )
      // sidecar 在 Rust setup 阶段已拉起，hello 事件可能早于监听到达，故乐观置为已连接。
      status.value = 'connected'
      return
    }

    // 浏览器开发：直连 WS
    status.value = 'connecting'
    ws = new WebSocket(devWsUrl)
    ws.onopen = () => { status.value = 'connected' }
    ws.onclose = () => { status.value = 'disconnected' }
    ws.onerror = () => { status.value = 'disconnected' }
    ws.onmessage = (m) => {
      try { push(JSON.parse(m.data as string)) } catch { /* 忽略坏帧 */ }
    }
  }

  async function run(objective: string) {
    reset()
    if (inTauri) {
      await call('agent_run', { objective })
      return
    }
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'run', objective }))
    }
  }

  async function confirm(requestId: string, approved: boolean) {
    if (inTauri) {
      // Tauri 2 命令参数为 camelCase：request_id → requestId
      await call('agent_confirm', { requestId, approved })
    } else if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'confirm', request_id: requestId, approved }))
    }
    confirmRequests.value = confirmRequests.value.filter((r) => r.requestId !== requestId)
  }

  return { status, events, tasks, report, confirmRequests, connect, run, confirm }
}
