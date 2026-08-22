import { spawn, type ChildProcess } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const DEFAULT_WS = 'ws://127.0.0.1:8765/ws'
let child: ChildProcess | null = null

interface NuxtLike {
  options: { dev: boolean }
  hook: (name: string, callback: () => void) => void
}

export default function devBackend(_inlineOptions: unknown, nuxt: NuxtLike) {
  if (!nuxt.options.dev) return
  if (process.env.TAURI_ENV_PLATFORM) return
  if (process.env.VITE_RUNTIME_WS && process.env.VITE_RUNTIME_WS !== DEFAULT_WS) return

  const repoRoot = fileURLToPath(new URL('../../..', import.meta.url))

  nuxt.hook('listen', () => {
    if (child) return
    child = spawn('uv', ['run', '--no-sync', 'python', '-m', 'demo_agent', '--port', '8765'], {
      cwd: repoRoot,
      stdio: 'inherit',
      env: process.env,
    })
    child.on('exit', () => { child = null })
  })

  nuxt.hook('close', () => {
    child?.kill()
    child = null
  })
}
