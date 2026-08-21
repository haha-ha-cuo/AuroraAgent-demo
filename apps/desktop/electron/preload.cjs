const { contextBridge } = require('electron')

const urlArg = process.argv.find((a) => a.startsWith('--agent-server-url='))
const wsUrl = urlArg ? urlArg.split('=').slice(1).join('=') : 'ws://127.0.0.1:8765/ws'

contextBridge.exposeInMainWorld('agentServer', { wsUrl })
