# 维护文档

文档内容位于 `docs/`，站点代码位于 `apps/docs/`。使用 pnpm 11。

## 本地预览

在文档仓库根目录执行：

```sh
cd apps/docs
pnpm install --frozen-lockfile
pnpm dev
```

打开终端显示的地址。修改 Markdown 后，页面会自动更新。

## 构建与发布

```sh
pnpm typecheck
pnpm build
```

静态文件输出到 `apps/docs/dist/`。文档或站点改动推送到 `main` 后，GitHub Actions 自动发布。

端口占用时使用 `pnpm dev --port 5174`。依赖安装失败时保留锁文件，检查终端错误后重试。
