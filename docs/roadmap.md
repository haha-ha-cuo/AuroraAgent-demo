# 路线图

> 路线图随项目进展滚动更新。当前处于**阶段三（桌面壳 MVP）**。

## 阶段一：文档站

- [x] 搭建 MkDocs Material 文档站
- [x] 固化项目定位、技术栈与参考架构
- [ ] 确定 Git 远端并启用文档自动部署（可选）

## 阶段二：Agent 核心

- [x] 最小纵向切片 demo：委派树 + 推理强度 + 能力特化层 + 本地 API 管理（见[运行最小 demo](getting-started/demo.md)）
- [ ] 落地 LangGraph 委派树与检查点（生产化）
- [ ] 推理强度从启发式升级为 LLM 自适应决策
- [ ] 打通 MCP 接入（当前 demo 以只读工具为占位）
- [ ] 实现能力特化层接口（第一版，作用域 / 优先级 / 回退）
- [x] 安全权限模型·确认门（风险分级 + 默认拒绝，[ADR-005](architecture/decisions.md#adr-005)）
- [ ] 安全权限模型·白名单 / dry-run / 沙箱（[ADR-005](architecture/decisions.md#adr-005)）
- [x] 最小 eval 集（12 个 fixture，校准任务识别与推理强度，[ADR-006](architecture/decisions.md#adr-006)）
- [x] eval 升级：judge 打分 + 强度分档对照实验（[ADR-006](architecture/decisions.md#adr-006)）

## 阶段三：桌面壳

- [x] 敲定桌面壳框架：Electron（+ React）
- [x] 打通桌面 UI 与本地 Python 运行时的通信（WebSocket，自动拉起运行时）
- [x] 前端交互：会话流 / 委派树可视化 / 确认门弹窗 / 事件流式输出
- [x] 流式 token 输出（`_live_worker` 切 stream + token 事件推送到 UI）
- [ ] 生产化：会话持久化、任务树交互（取消/重试）

## 阶段四：发布分发

- 三平台（macOS / Windows / Linux）打包
- 签名、自动更新与分发渠道
- 稳定性与安全加固
