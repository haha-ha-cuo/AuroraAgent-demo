import { ref } from 'vue'

export type ThemeMode = 'light' | 'dark' | 'system'

const KEY = 'demo-docs-theme'

function loadMode(): ThemeMode {
  const v = localStorage.getItem(KEY)
  return v === 'light' || v === 'dark' || v === 'system' ? v : 'system'
}

const mode = ref<ThemeMode>(loadMode())
const isDark = ref(false)
const systemDark = ref(false)

const mql = window.matchMedia('(prefers-color-scheme: dark)')
systemDark.value = mql.matches
mql.addEventListener('change', (e) => {
  systemDark.value = e.matches
  apply()
})

function apply() {
  const dark = mode.value === 'dark' || (mode.value === 'system' && systemDark.value)
  isDark.value = dark
  document.documentElement.classList.toggle('dark', dark)
  localStorage.setItem(KEY, mode.value)
}

apply()

export function useTheme() {
  return {
    mode,
    isDark,
    setMode(m: ThemeMode) {
      mode.value = m
      apply()
    },
  }
}
