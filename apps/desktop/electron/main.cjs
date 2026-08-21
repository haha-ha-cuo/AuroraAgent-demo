const { app, BrowserWindow } = require('electron')
const { spawn } = require('child_process')
const fs = require('fs')
const path = require('path')

const repoRoot = path.resolve(__dirname, '../../..')
const DEFAULT_PORT = process.env.DEMO_AGENT_PORT || '8765'
const SERVER_URL = process.env.DEMO_AGENT_SERVER_URL || `ws://127.0.0.1:${DEFAULT_PORT}/ws`
const RENDERER_URL = process.env.ELECTRON_RENDERER_URL || 'http://127.0.0.1:5173'

function pythonCommand() {
  if (process.env.DEMO_AGENT_PYTHON) {
    return { bin: process.env.DEMO_AGENT_PYTHON, args: [] }
  }
  const venvPython = path.join(repoRoot, '.venv', 'bin', 'python')
  if (fs.existsSync(venvPython)) {
    return { bin: venvPython, args: [] }
  }
  // 兜底：用 uv 运行（在项目根目录）
  return { bin: 'uv', args: ['run', 'python'] }
}

function startPythonServer() {
  if (process.env.DEMO_AGENT_SERVER_URL) return null // 已指定外部服务，不自行拉起
  const { bin, args } = pythonCommand()
  const child = spawn(bin, [...args, '-m', 'demo_agent.server', '--port', DEFAULT_PORT], {
    cwd: repoRoot,
    stdio: 'inherit',
  })
  child.on('error', (err) => {
    console.warn('[agent] 无法启动 Python 服务（可能已在运行或 .venv 不存在）:', err.message)
  })
  child.on('exit', (code) => {
    if (code && code !== 0) console.warn('[agent] Python 服务退出，code =', code)
  })
  return child
}

let mainWindow = null
let pythonProc = null

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    title: 'Demo Agent',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      additionalArguments: [`--agent-server-url=${SERVER_URL}`],
    },
  })

  // 开发期加载 Vite dev server；打包后改 loadFile(dist/index.html)
  const loadWithRetry = async () => {
    for (let i = 0; i < 20; i++) {
      try {
        await mainWindow.loadURL(RENDERER_URL)
        return
      } catch (_) {
        await new Promise((r) => setTimeout(r, 500))
      }
    }
    console.error('[agent] 无法连接渲染层 dev server:', RENDERER_URL)
  }
  loadWithRetry()

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

app.whenReady().then(() => {
  pythonProc = startPythonServer()
  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (pythonProc) pythonProc.kill()
  if (process.platform !== 'darwin') app.quit()
})
