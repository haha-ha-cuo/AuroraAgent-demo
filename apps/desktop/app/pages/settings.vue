<script setup lang="ts">
import { NButton, NCard, NDescriptions, NDescriptionsItem, NForm, NFormItem, NIcon, NInput, NRadioButton, NRadioGroup, NSelect, NTag, useDialog, useMessage } from 'naive-ui'
import { Database, DeviceDesktop, Refresh, ShieldLock, Trash } from '@vicons/tabler'
import type { ThemePreference } from '~/types/agent'

const sessions = useSessionStore(); const runtime = useRuntimeStore(); const ui = useUiStore()
const dialog = useDialog(); const message = useMessage(); const saving = ref(false); const restarting = ref(false)
const form = reactive({ provider: 'mock', baseUrl: '', model: '', apiKey: '' })
const desktopMode = computed(() => import.meta.client && '__TAURI_INTERNALS__' in window)
watch(() => runtime.settings, (settings) => Object.assign(form, { provider: settings.provider, baseUrl: settings.baseUrl, model: settings.model, apiKey: '' }), { immediate: true, deep: true })
useHead({ title: '设置' })

async function save() {
  saving.value = true
  try { await runtime.saveSettings({ ...form }); form.apiKey = ''; message.success('模型设置已安全保存') }
  catch (error) { message.error(error instanceof Error ? error.message : String(error)) }
  finally { saving.value = false }
}
async function restart() { restarting.value = true; try { await runtime.restart(); message.success('运行时已重启') } catch (error) { message.error(String(error)) } finally { restarting.value = false } }
function confirmClear() {
  dialog.warning({ title: '清除全部历史？', content: `SQLite 中的 ${sessions.sessions.length} 个会话及其运行记录将永久删除。模型密钥不会受影响。`, positiveText: '清除', negativeText: '取消', onPositiveClick: async () => { await sessions.clearAll(); message.success('历史已清除'); await navigateTo('/') } })
}
</script>

<template>
  <main class="settings-page app-scrollbar">
    <header class="settings-header"><p>应用偏好与运行时</p><h1>设置</h1></header>
    <div class="settings-grid">
      <NCard title="外观"><template #header-extra><NIcon :component="DeviceDesktop" :size="18" /></template>
        <div class="setting-row"><div><strong>主题</strong><p>可跟随系统，也可锁定浅色或深色。</p></div><NRadioGroup :value="ui.theme" size="small" @update:value="ui.setTheme($event as ThemePreference)"><NRadioButton value="system">系统</NRadioButton><NRadioButton value="light">浅色</NRadioButton><NRadioButton value="dark">深色</NRadioButton></NRadioGroup></div>
      </NCard>

      <NCard title="模型"><template #header-extra><NIcon :component="ShieldLock" :size="18" /></template>
        <NForm label-placement="top" class="model-form">
          <div class="form-grid">
            <NFormItem label="Provider"><NSelect v-model:value="form.provider" :options="[{label:'Mock（无需密钥）',value:'mock'},{label:'OpenAI 兼容',value:'openai'}]" /></NFormItem>
            <NFormItem label="模型"><NInput v-model:value="form.model" placeholder="例如 gpt-5" /></NFormItem>
          </div>
          <NFormItem label="Base URL"><NInput v-model:value="form.baseUrl" placeholder="https://api.openai.com/v1" /></NFormItem>
          <NFormItem label="API Key"><NInput v-model:value="form.apiKey" type="password" show-password-on="click" :disabled="!desktopMode" :placeholder="!desktopMode ? '浏览器开发模式请通过环境变量配置' : runtime.settings.hasApiKey ? '已存入系统钥匙串；留空保持不变' : '仅写入系统钥匙串'" autocomplete="new-password" /></NFormItem>
          <div class="form-actions"><span>Provider 选择「Mock」即启用确定性 Mock 模式</span><NButton type="primary" :loading="saving" @click="save">保存设置</NButton></div>
        </NForm>
      </NCard>

      <NCard title="Agent 运行时">
        <NDescriptions label-placement="left" :column="1" size="small">
          <NDescriptionsItem label="连接"><NTag size="small" :bordered="false">{{ runtime.connectionStatus }}</NTag></NDescriptionsItem>
          <NDescriptionsItem label="模式">{{ runtime.info.mode || '—' }}</NDescriptionsItem>
          <NDescriptionsItem label="活跃运行">{{ runtime.info.activeRuns }}</NDescriptionsItem>
          <NDescriptionsItem label="数据库"><span class="db-path">{{ runtime.info.databasePath || '等待运行时上报' }}</span></NDescriptionsItem>
        </NDescriptions>
        <NButton class="restart-button" secondary :loading="restarting" @click="restart"><template #icon><NIcon :component="Refresh" /></template>重启运行时</NButton>
      </NCard>

      <NCard title="本地数据"><template #header-extra><NIcon :component="Database" :size="18" /></template>
        <div class="setting-row"><div><strong>会话历史</strong><p>SQLite 保存 {{ sessions.sessions.length }} 个会话；localStorage 仅保留界面偏好和迁移标记。</p></div><NButton type="error" secondary :disabled="!sessions.sessions.length" @click="confirmClear"><template #icon><NIcon :component="Trash" /></template>清除</NButton></div>
      </NCard>
      <NCard title="关于"><NDescriptions label-placement="left" :column="1" size="small"><NDescriptionsItem label="产品">Demo Agent</NDescriptionsItem><NDescriptionsItem label="版本">0.1.0</NDescriptionsItem><NDescriptionsItem label="协议">Runtime Protocol v1</NDescriptionsItem></NDescriptions></NCard>
    </div>
  </main>
</template>

<style scoped>
.settings-page{width:100%;height:100%;overflow:auto;padding:44px 36px 64px}.settings-header,.settings-grid{width:min(780px,100%);margin-right:auto;margin-left:auto}.settings-header{margin-bottom:21px}.settings-header p{margin:0 0 5px;color:var(--text-muted);font-size:11px;font-weight:650;letter-spacing:.06em}.settings-header h1{margin:0;font-size:27px;letter-spacing:-.03em}.settings-grid{display:grid;gap:12px}.settings-grid :deep(.n-card){border-radius:11px;background:var(--surface)}.setting-row{display:flex;align-items:center;justify-content:space-between;gap:20px}.setting-row strong{font-size:13px}.setting-row p{margin:4px 0 0;color:var(--text-muted);font-size:12px;line-height:1.5}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.model-form :deep(.n-form-item){margin-bottom:7px}.form-actions{display:flex;align-items:center;justify-content:space-between;color:var(--text-muted);font-size:12px}.restart-button{margin-top:14px}.db-path{overflow-wrap:anywhere;color:var(--text-muted);font-size:11px}@media(max-width:680px){.settings-page{padding:32px 16px 48px}.setting-row{align-items:flex-start;flex-direction:column}.form-grid{grid-template-columns:1fr}}
</style>
