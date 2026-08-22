<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  NBackTop,
  NButton,
  NConfigProvider,
  NDrawer,
  NDrawerContent,
  NDropdown,
  NGlobalStyle,
  NMessageProvider,
  dateZhCN,
  darkTheme,
  zhCN,
  type GlobalThemeOverrides,
} from 'naive-ui'
import SideNav from './components/SideNav.vue'
import { SITE } from './site'
import { useTheme, type ThemeMode } from './composables/theme'

const { mode, isDark, setMode } = useTheme()

const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#4C6FFF',
    primaryColorHover: '#6E88FF',
    primaryColorPressed: '#3B55DB',
    primaryColorSuppl: '#4C6FFF',
    borderRadius: '6px',
  },
}

const drawerOpen = ref(false)
const isMobile = ref(false)
const mql = window.matchMedia('(max-width: 900px)')
isMobile.value = mql.matches
mql.addEventListener('change', (e) => (isMobile.value = e.matches))

const themeOptions = [
  { label: '浅色', key: 'light' },
  { label: '深色', key: 'dark' },
  { label: '跟随系统', key: 'system' },
]

const themeTitle = computed(() => {
  if (mode.value === 'light') return '浅色模式'
  if (mode.value === 'dark') return '深色模式'
  return '跟随系统'
})

function onThemeSelect(key: string) {
  setMode(key as ThemeMode)
}

function onNavigate() {
  drawerOpen.value = false
}
</script>

<template>
  <n-config-provider
    :theme="isDark ? darkTheme : null"
    :theme-overrides="themeOverrides"
    :locale="zhCN"
    :date-locale="dateZhCN"
  >
    <n-global-style />
    <n-message-provider>
      <div class="app-shell">
        <header class="app-header">
          <div class="header-left">
            <n-button
              v-if="isMobile"
              quaternary
              circle
              class="header-btn"
              aria-label="打开菜单"
              @click="drawerOpen = true"
            >
              <template #icon>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <line x1="3" y1="6" x2="21" y2="6" />
                  <line x1="3" y1="12" x2="21" y2="12" />
                  <line x1="3" y1="18" x2="21" y2="18" />
                </svg>
              </template>
            </n-button>

            <router-link to="/" class="brand">
              <span class="brand-mark">◆</span>
              <span class="brand-text">Demo · AI Agent</span>
              <span class="brand-sub">文档</span>
            </router-link>
          </div>

          <div class="header-right">
            <n-dropdown :options="themeOptions" trigger="click" @select="onThemeSelect">
              <n-button quaternary circle class="header-btn" :title="themeTitle">
                <template #icon>
                  <svg
                    v-if="mode === 'light'"
                    xmlns="http://www.w3.org/2000/svg"
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  >
                    <circle cx="12" cy="12" r="5" />
                    <line x1="12" y1="1" x2="12" y2="3" />
                    <line x1="12" y1="21" x2="12" y2="23" />
                    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
                    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
                    <line x1="1" y1="12" x2="3" y2="12" />
                    <line x1="21" y1="12" x2="23" y2="12" />
                    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
                    <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
                  </svg>
                  <svg
                    v-else-if="mode === 'dark'"
                    xmlns="http://www.w3.org/2000/svg"
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  >
                    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
                  </svg>
                  <svg
                    v-else
                    xmlns="http://www.w3.org/2000/svg"
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  >
                    <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
                    <line x1="8" y1="21" x2="16" y2="21" />
                    <line x1="12" y1="17" x2="12" y2="21" />
                  </svg>
                </template>
              </n-button>
            </n-dropdown>

            <n-button
              quaternary
              circle
              class="header-btn"
              tag="a"
              :href="SITE.repo"
              target="_blank"
              aria-label="GitHub 仓库"
              title="GitHub 仓库"
            >
              <template #icon>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                >
                  <path
                    d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"
                  />
                </svg>
              </template>
            </n-button>
          </div>
        </header>

        <div class="app-body">
          <aside v-show="!isMobile" class="app-sider">
            <SideNav />
          </aside>
          <main class="app-content">
            <router-view />
          </main>
        </div>

        <n-back-top :right="40" :bottom="40" :visibility-height="400" />

        <n-drawer v-model:show="drawerOpen" placement="left" :width="300">
          <n-drawer-content title="目录" closable>
            <SideNav @navigate="onNavigate" />
          </n-drawer-content>
        </n-drawer>
      </div>
    </n-message-provider>
  </n-config-provider>
</template>
