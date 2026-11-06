# Aurora 文档

[阅读指南](https://haha-ha-cuo.github.io/AuroraAgent-demo/) · [应用源码](https://github.com/AuroraBot-Dev/AuroraHarness)

本仓库托管使用指南与架构文档。当前应用在 AuroraHarness 开发，旧示例说明保留在 [README.legacy.md](README.legacy.md)。

## 本地预览

```sh
cd apps/docs
pnpm install --frozen-lockfile
pnpm dev
```

使用 pnpm 11，打开终端显示的地址。内容位于 `docs/`，站点代码位于 `apps/docs/`。

## 验证与发布

```sh
pnpm typecheck
pnpm build
```

文档或站点改动推送至 `main` 后自动部署。写作时先讲操作步骤，架构与验证记录另放；用户指南中的命令和入口必须与实际版本一致。
