<script setup lang="ts">
// 骨架页面：占位 UI，逐步替换为真实交互。
// 运行时事件经 useRuntime 接入（开发态直连 WS，打包态 TODO 走 Tauri stdio 中继）。
const { status, tasks, report, confirmRequests, connect, run, confirm } = useRuntime()
const { inTauri } = useIpc()

const objective = ref('')

onMounted(() => {
  connect()
})

function submit() {
  if (!objective.value.trim()) return
  run(objective.value.trim())
}
</script>

<template>
  <main class="shell">
    <header class="bar">
      <h1>Demo Agent <span class="tag">骨架</span></h1>
      <div class="meta">
        <span :class="['dot', status]" />
        <span>{{ status }}</span>
        <span class="muted">· Tauri: {{ inTauri ? 'in' : 'browser' }}</span>
      </div>
    </header>

    <section class="composer">
      <textarea
        v-model="objective"
        rows="3"
        placeholder="输入目标，例如：列出项目文件结构，并阅读 README.md 总结项目定位"
      />
      <button :disabled="status !== 'connected'" @click="submit">运行</button>
    </section>

    <section class="grid">
      <div class="card">
        <h2>委派树</h2>
        <ul v-if="tasks.length" class="tree">
          <li v-for="t in tasks" :key="t.id">
            <span class="effort" :class="t.effort">{{ t.effort }}</span>
            {{ t.id }} — {{ t.description }}
          </li>
        </ul>
        <p v-else class="muted">（暂无任务）</p>
      </div>

      <div class="card">
        <h2>确认门</h2>
        <template v-if="confirmRequests.length">
          <div v-for="r in confirmRequests" :key="r.requestId" class="confirm">
            <p>[{{ r.risk }}] {{ r.action }}</p>
            <button @click="confirm(r.requestId, true)">允许</button>
            <button class="danger" @click="confirm(r.requestId, false)">拒绝</button>
          </div>
        </template>
        <p v-else class="muted">（无待确认操作）</p>
      </div>

      <div class="card wide">
        <h2>汇总报告</h2>
        <pre v-if="report">{{ report }}</pre>
        <p v-else class="muted">（暂无报告）</p>
      </div>
    </section>
  </main>
</template>

<style scoped>
.shell { max-width: 1080px; margin: 0 auto; padding: 24px; font-family: system-ui, sans-serif; }
.bar { display: flex; align-items: center; justify-content: space-between; }
.tag { font-size: 12px; color: #666; border: 1px solid #ddd; border-radius: 4px; padding: 1px 6px; margin-left: 8px; }
.meta { display: flex; align-items: center; gap: 8px; font-size: 14px; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: #bbb; display: inline-block; }
.dot.connected { background: #22c55e; }
.dot.connecting { background: #eab308; }
.dot.disconnected { background: #ef4444; }
.muted { color: #888; }
.composer { display: flex; gap: 12px; margin: 16px 0; align-items: flex-end; }
.composer textarea { flex: 1; padding: 10px; font: inherit; border: 1px solid #ddd; border-radius: 8px; resize: vertical; }
button { padding: 8px 16px; border: none; border-radius: 8px; background: #6366f1; color: #fff; cursor: pointer; }
button:disabled { opacity: .5; cursor: not-allowed; }
button.danger { background: #ef4444; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.card { border: 1px solid #eee; border-radius: 10px; padding: 16px; }
.card h2 { margin: 0 0 12px; font-size: 15px; }
.card.wide { grid-column: 1 / -1; }
.tree { list-style: none; padding: 0; margin: 0; }
.tree li { padding: 4px 0; font-size: 14px; }
.effort { display: inline-block; min-width: 52px; text-align: center; font-size: 11px; border-radius: 4px; padding: 1px 6px; margin-right: 8px; color: #fff; }
.effort.low { background: #22c55e; }
.effort.medium { background: #eab308; }
.effort.high { background: #ef4444; }
.confirm { margin-bottom: 12px; }
.confirm button { margin-right: 8px; }
pre { white-space: pre-wrap; background: #f6f7f9; padding: 12px; border-radius: 8px; font-size: 13px; }
</style>
