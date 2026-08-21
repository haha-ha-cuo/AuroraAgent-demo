import { useEffect, useRef, useState } from 'react'

const WS_URL = window.agentServer?.wsUrl || 'ws://127.0.0.1:8765/ws'

const DEFAULT_OBJECTIVE = '列出项目文件结构，并阅读 README.md 总结项目定位'

export default function App() {
  const [connected, setConnected] = useState(false)
  const [mode, setMode] = useState('')
  const [model, setModel] = useState('')
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState([])
  const [tasks, setTasks] = useState([])
  const [taskStates, setTaskStates] = useState({})
  const [pendingConfirm, setPendingConfirm] = useState(null)
  const [running, setRunning] = useState(false)
  const wsRef = useRef(null)

  useEffect(() => {
    const ws = new WebSocket(WS_URL)
    wsRef.current = ws
    ws.onopen = () => setConnected(true)
    ws.onclose = () => setConnected(false)
    ws.onmessage = (e) => {
      try {
        handleEvent(JSON.parse(e.data))
      } catch (_) {
        /* ignore */
      }
    }
    return () => ws.close()
  }, [])

  function handleEvent(ev) {
    switch (ev.type) {
      case 'hello':
        setMode(ev.mode)
        setModel(ev.model)
        break
      case 'run_start':
        setRunning(true)
        setTasks([])
        setTaskStates({})
        setMessages((m) => [...m, { role: 'user', text: ev.objective }])
        break
      case 'plan':
        setTasks(ev.tasks)
        setTaskStates(
          Object.fromEntries(ev.tasks.map((t) => [t.id, { status: 'pending' }])),
        )
        break
      case 'task_start':
        setTaskStates((s) => ({
          ...s,
          [ev.task_id]: {
            ...s[ev.task_id],
            status: 'running',
            description: ev.description,
            effort: ev.effort,
          },
        }))
        break
      case 'task_result':
        setTaskStates((s) => ({
          ...s,
          [ev.task_id]: { ...s[ev.task_id], status: 'done', result: ev.result },
        }))
        break
      case 'report':
        setMessages((m) => [...m, { role: 'agent', text: ev.report }])
        break
      case 'confirm_request':
        setPendingConfirm({
          request_id: ev.request_id,
          action: ev.action,
          risk: ev.risk,
        })
        break
      case 'done':
        setRunning(false)
        break
      case 'error':
        setRunning(false)
        setMessages((m) => [...m, { role: 'error', text: ev.message }])
        break
      default:
        break
    }
  }

  function sendRun() {
    const objective = input.trim()
    if (!objective || !wsRef.current) return
    wsRef.current.send(JSON.stringify({ type: 'run', objective }))
    setInput('')
  }

  function answerConfirm(approved) {
    if (!pendingConfirm || !wsRef.current) return
    wsRef.current.send(
      JSON.stringify({ type: 'confirm', request_id: pendingConfirm.request_id, approved }),
    )
    setPendingConfirm(null)
  }

  return (
    <div className="app">
      <header className="topbar">
        <h1>Demo · CodeX-like AI Agent</h1>
        <span className={`status ${connected ? 'ok' : 'down'}`}>
          {connected ? `已连接 · ${mode} · ${model}` : '未连接'}
        </span>
      </header>

      <div className="layout">
        <main className="chat">
          <div className="messages">
            {messages.length === 0 && !running && (
              <p className="hint">输入目标，Agent 会把任务委派给子 Agent 并逐步汇报。</p>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`msg ${m.role}`}>
                {m.text}
              </div>
            ))}
            {running && <div className="msg agent thinking">正在推进…</div>}
          </div>
          <form
            className="composer"
            onSubmit={(e) => {
              e.preventDefault()
              sendRun()
            }}
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={DEFAULT_OBJECTIVE}
            />
            <button type="submit" disabled={!connected || running}>
              运行
            </button>
          </form>
        </main>

        <aside className="tree">
          <h2>委派树</h2>
          {tasks.length === 0 ? (
            <p className="hint">等待任务…</p>
          ) : (
            <ul>
              {tasks.map((t) => {
                const st = taskStates[t.id] || {}
                return (
                  <li key={t.id}>
                    <div className="task-head">
                      <span className={`dot ${st.status || 'pending'}`} />
                      <span className="task-name">{t.id}</span>
                      <span className="effort">[{t.effort}]</span>
                      <span className="desc">{st.description || t.description}</span>
                    </div>
                    {st.status === 'done' && <pre className="result">{st.result}</pre>}
                  </li>
                )
              })}
            </ul>
          )}
        </aside>
      </div>

      {pendingConfirm && (
        <div className="modal">
          <div className="modal-box">
            <h3>
              ⚠ 需要确认 <span className="risk">[{pendingConfirm.risk}]</span>
            </h3>
            <p>{pendingConfirm.action}</p>
            <div className="modal-actions">
              <button onClick={() => answerConfirm(false)}>拒绝</button>
              <button className="primary" onClick={() => answerConfirm(true)}>
                允许
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
