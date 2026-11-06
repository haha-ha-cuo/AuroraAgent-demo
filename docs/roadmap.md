# 路线图

> 路线图随项目进展滚动更新。当前处于**阶段三（桌面壳 MVP）**。

## 阶段一：文档站

- [x] 搭建文档站（Vite + Vue 3 + naive-ui）
- [x] 固化项目定位、技术栈与参考架构
- [x] 确定 Git 远端并启用文档自动部署（GitHub Actions → GitHub Pages）

## 阶段二：Agent 核心

- [x] 最小纵向切片 demo：委派树 + 推理强度 + 能力特化层 + 本地 API 管理（见[运行最小 demo](getting-started/demo.md)）
- [ ] 落地 LangGraph 委派树与检查点（生产化）
- AuroraHarness 开发版已支持受限递归、计划校验、共享任务预算，以及人工输入等待点的同轮恢复。同计划内支持依赖调度、只读子树并行和阻断任务的局部重试。扩展工具的重启恢复与失败后的自动重规划仍待实现。见[执行校验与资源限制](architecture/execution-runtime.md)。
- [ ] 推理强度从启发式升级为 LLM 自适应决策
- [ ] 打通 MCP 接入（当前 demo 以只读工具为占位）
- [ ] 实现能力特化层接口（AuroraHarness 开发中：作用域、优先级、原子回退、权限交集与本轮能力清单；以实现合并和发布验收为准）
- [ ] 能力清单可视化与声明式配方（新增设计，尚未实现；见[能力特化层](architecture/capability-layer.md#本轮能力清单)）
- [x] 安全权限模型·确认门（风险分级 + 默认拒绝，[ADR-005](architecture/decisions.md#adr-005)）
- [ ] 安全权限模型·白名单 / dry-run / 沙箱（[ADR-005](architecture/decisions.md#adr-005)）
- [x] 最小 eval 集（12 个 fixture，校准任务识别与推理强度，[ADR-006](architecture/decisions.md#adr-006)）
- [x] eval 升级：judge 打分 + 强度分档对照实验（[ADR-006](architecture/decisions.md#adr-006)）

## 阶段三：桌面壳

- [x] 用 Electron（+React）验证壳与 Python 运行时的通信闭环（WebSocket + 自动拉起）
- [x] 前端交互：会话流 / 委派树可视化 / 确认门弹窗 / 事件流式输出
- [x] 流式 token 输出（`_live_worker` 切 stream + token 事件推送到 UI）
- [x] 敲定桌面壳选型：Tauri 2 + Nuxt（Vue3+TS，SPA），见 [ADR-007](architecture/decisions.md#adr-007)
- [x] 桌面应用架构规划落地（[architecture/desktop.md](architecture/desktop.md)）
- [x] 骨架落地：Tauri 2 + Nuxt(SPA) 脚手架、`server.py` 增 `--stdio` 传输、Rust stdio 中继骨架
- [x] 前端接通 stdio 中继（`useRuntime` 接入 Tauri `invoke`/`listen`）+ MVP 交互（会话/委派树/确认门/流式）
- [ ] Rust 核心：sidecar 监督 + 钥匙串 + 单实例
- [ ] 生产化：会话持久化、任务树交互（取消/重试）
- [ ] AuroraHarness 对话与调用轨迹发布验收（开发工作树已实现精简时间线与苹方字体；[使用方式](architecture/conversation-canvas.md)）

## 阶段四：发布分发

- Python sidecar 三平台打包（python-build-standalone + uv，CI 矩阵）
- 三平台（macOS / Windows / Linux）Tauri 打包
- 签名（macOS 公证 / Windows 签名）、自动更新与分发渠道
- 稳定性与安全加固
