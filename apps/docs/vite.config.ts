import { fileURLToPath, URL } from 'node:url'
import { readFileSync, writeFileSync } from 'node:fs'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// GitHub Pages 项目站点路径：https://<user>.github.io/<repo>/
// 自定义域名时可通过环境变量 VITE_BASE='/' 覆盖。
const REPO_BASE = '/AuroraAgent-demo/'

export default defineConfig(({ command }) => {
  const isBuild = command === 'build'
  const base = process.env.VITE_BASE ?? (isBuild ? REPO_BASE : '/')

  return {
    base,
    plugins: [
      vue(),
      // GitHub Pages 无 SPA 回退：把 index.html 复制为 404.html，
      // 让深链（如 /<repo>/architecture/overview）刷新时也能被 SPA 接管。
      {
        name: 'copy-404',
        apply: 'build',
        closeBundle() {
          const out = fileURLToPath(new URL('dist/index.html', import.meta.url))
          const dest = fileURLToPath(new URL('dist/404.html', import.meta.url))
          writeFileSync(dest, readFileSync(out))
        },
      },
    ],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('src', import.meta.url)),
      },
    },
    server: {
      host: '127.0.0.1',
      port: 5173,
      // 允许 dev server 读取仓库根目录 docs/**（Markdown 单一内容源）
      fs: {
        allow: [fileURLToPath(new URL('../../', import.meta.url))],
      },
    },
    build: {
      outDir: 'dist',
      chunkSizeWarningLimit: 1400,
    },
  }
})
