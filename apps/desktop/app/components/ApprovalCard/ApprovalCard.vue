<script setup lang="ts">
import { NButton, NIcon, NTag } from 'naive-ui'
import { AlertCircle, Check, X } from '@vicons/tabler'
import type { ApprovalRequest } from '~/types/agent'

defineProps<{ request: ApprovalRequest }>()
const emit = defineEmits<{ decide: [requestId: string, approved: boolean] }>()
</script>

<template>
  <article class="approval-card">
    <div class="approval-icon"><NIcon :component="AlertCircle" :size="19" /></div>
    <div class="approval-copy">
      <div class="approval-title">需要你的确认 <NTag size="small" :bordered="false">{{ request.risk }}</NTag></div>
      <p>{{ request.action }}</p><p v-if="request.details">{{ request.details }}</p>
    </div>
    <div class="approval-actions">
      <NButton size="small" @click="emit('decide', request.id, false)"><template #icon><NIcon :component="X" /></template>拒绝</NButton>
      <NButton size="small" type="primary" @click="emit('decide', request.id, true)"><template #icon><NIcon :component="Check" /></template>允许</NButton>
    </div>
  </article>
</template>

<style scoped>
.approval-card { display: flex; align-items: flex-start; gap: 12px; margin: 14px 0; padding: 14px; border: 1px solid var(--border); border-radius: 10px; background: var(--surface); }
.approval-icon { display: grid; width: 32px; height: 32px; flex: 0 0 32px; place-items: center; border-radius: 8px; background: rgb(214 158 46 / 12%); color: #b7791f; }
.approval-copy { min-width: 0; flex: 1; }
.approval-title { display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 650; }
.approval-copy p { margin: 5px 0 0; color: var(--text-muted); font-size: 12px; line-height: 1.55; }
.approval-actions { display: flex; gap: 8px; }
@media (max-width: 680px) { .approval-card { flex-wrap: wrap; } .approval-actions { width: 100%; justify-content: flex-end; } }
</style>
