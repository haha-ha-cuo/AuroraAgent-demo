# 快速开始

以下以 AuroraHarness 开发版为准。先准备 [uv、Node.js 24 与 pnpm 11](prerequisites.md)。

## 1. 启动应用

获取 [AuroraHarness 源码](https://github.com/AuroraBot-Dev/AuroraHarness)，在仓库根目录执行：

```sh
node scripts/tasks.mjs setup
node scripts/tasks.mjs dev-web
```

打开终端显示的 Local 地址。

## 2. 配置模型

1. 进入「设置 → 模型与协作」，添加供应商，填写端点与 API Key。
2. 添加模型，填写供应商实际支持的模型 ID。
3. 在「Agent」中编辑默认角色，选择刚添加的模型并保存。

## 3. 发送第一个任务

在工作台添加工作区，输入「读取 `README.md`」并发送。写入或执行操作需要确认；运行中可点击停止。

接下来：[对话与调用轨迹](../architecture/conversation-canvas.md)。
