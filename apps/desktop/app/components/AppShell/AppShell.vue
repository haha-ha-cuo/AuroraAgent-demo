<script setup lang="ts">
import { NLayout, NLayoutContent, NLayoutSider } from 'naive-ui'

const ui = useUiStore()
const compact = ref(false)
const collapsed = computed(() => compact.value || ui.sidebarCollapsed)
let compactQuery: MediaQueryList | null = null

function syncCompact(event?: MediaQueryListEvent) {
  compact.value = event?.matches ?? compactQuery?.matches ?? false
}

onMounted(() => {
  compactQuery = window.matchMedia('(max-width: 860px)')
  syncCompact()
  compactQuery.addEventListener('change', syncCompact)
})

onBeforeUnmount(() => compactQuery?.removeEventListener('change', syncCompact))
</script>

<template>
  <NLayout class="app-shell" has-sider>
    <NLayoutSider
      class="app-sider"
      :width="collapsed ? 68 : 280"
      :native-scrollbar="false"
      bordered
    >
      <AppSidebar :collapsed="collapsed" />
    </NLayoutSider>
    <NLayoutContent class="app-content" content-style="height: 100%; overflow: hidden;">
      <slot />
    </NLayoutContent>
  </NLayout>
</template>

<style scoped>
.app-shell {
  width: 100vw;
  height: 100vh;
  height: 100dvh;
  padding: 8px;
  gap: 8px;
  background: var(--shell-bg);
  overflow: hidden;
}

.app-sider {
  height: calc(100vh - 16px);
  height: calc(100dvh - 16px);
  border: 1px solid var(--glass-border) !important;
  border-radius: 16px;
  background: var(--sidebar-glass) !important;
  box-shadow: var(--glass-shadow);
  backdrop-filter: blur(22px) saturate(125%);
  -webkit-backdrop-filter: blur(22px) saturate(125%);
  overflow: hidden;
}

.app-sider :deep(.n-layout-sider-scroll-container) {
  background: transparent;
}

.app-content {
  min-width: 0;
  margin-left: 8px;
  height: calc(100vh - 16px);
  height: calc(100dvh - 16px);
  border: 1px solid var(--glass-border);
  border-radius: 16px;
  background: var(--content-glass);
  box-shadow: var(--glass-shadow-soft);
  overflow: hidden;
}

@media (max-width: 680px) {
  .app-shell { padding: 5px; gap: 5px; }
  .app-content { margin-left: 5px; }
  .app-sider, .app-content {
    height: calc(100dvh - 10px);
    border-radius: 13px;
  }
}
</style>
