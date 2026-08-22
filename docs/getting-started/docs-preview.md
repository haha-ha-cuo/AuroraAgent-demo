# 文档本地预览

文档站基于 **Vite + Vue 3 + TypeScript + naive-ui** 构建，Markdown 内容仍以 `docs/` 为唯一内容源，站点代码位于 `apps/docs/`，前端依赖用 pnpm 管理。

## 前置条件

- [Node.js](https://nodejs.org/)（建议 LTS）
- [pnpm](https://pnpm.io/)

## 安装依赖

```bash
cd apps/docs
pnpm install
```

## 启动本地预览

```bash
cd apps/docs
pnpm dev
```

浏览器打开 [http://127.0.0.1:5173](http://127.0.0.1:5173) 即可实时预览。修改 `docs/` 下的 Markdown 或 `apps/docs/src/` 下的源码后，页面会自动热更新。

## 构建静态站点

```bash
cd apps/docs
pnpm build
```

- 产物输出到 `apps/docs/dist/` 目录（已被 `.gitignore` 忽略）。
- 构建时会生成 `404.html`（用于 GitHub Pages 的 SPA 深链回退），并把资源前缀设为 `/AuroraAgent-demo/`。
- 改为自定义域名时，可用环境变量覆盖资源前缀：`VITE_BASE='/' pnpm build`。

## 发布到 GitHub Pages

推送 `main` 分支后，`.github/workflows/deploy-docs.yml` 会自动构建并发布到 GitHub Pages（需在仓库 Settings → Pages 中将 Source 设为 **GitHub Actions**）。发布地址：<https://haha-ha-cuo.github.io/AuroraAgent-demo/>。

## 常见问题

### 依赖安装失败

删除本地锁文件与依赖目录后重试：

```bash
cd apps/docs
rm -rf node_modules pnpm-lock.yaml
pnpm install
```

### 端口被占用

`pnpm dev` 默认占用 5173 端口，可在 `apps/docs/vite.config.ts` 的 `server.port` 中修改。
