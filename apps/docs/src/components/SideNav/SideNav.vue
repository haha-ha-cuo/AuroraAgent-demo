<script setup lang="ts">
import { computed } from 'vue'
import { NMenu, type MenuOption } from 'naive-ui'
import { useRoute, useRouter } from 'vue-router'
import { NAV, slugToPath, type NavGroup, type NavLeaf } from '../../manifest'

const emit = defineEmits<{ navigate: [path: string] }>()

const route = useRoute()
const router = useRouter()

function isGroup(item: NavGroup | NavLeaf): item is NavGroup {
  return 'children' in item
}

const options = computed<MenuOption[]>(() =>
  NAV.map((item, i) => {
    if (isGroup(item)) {
      return {
        type: 'group',
        label: item.label,
        key: `group-${i}-${item.label}`,
        children: item.children.map((leaf) => ({
          label: leaf.label,
          key: slugToPath(leaf.slug),
        })),
      } as MenuOption
    }
    return { label: item.label, key: slugToPath(item.slug) } as MenuOption
  }),
)

const activeKey = computed(() => route.path)

function onSelect(key: string) {
  router.push(key)
  emit('navigate', key)
}
</script>

<template>
  <n-menu
    :options="options"
    :value="activeKey"
    :indent="20"
    :root-indent="18"
    @update:value="onSelect"
  />
</template>
