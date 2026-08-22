# 桌面前端路由与后端接入

本文描述 Nuxt 桌面前端的三个业务路由及其后端数据依赖。传输层字段、方法和事件的权威定义见[运行时协议 v1](runtime-protocol.md)，桌面进程边界见[桌面应用架构](desktop.md)。

## 共同约束

- Nuxt 运行在 SPA 模式，页面路由为 `/`、`/projects/:projectId`、`/sessions/:sessionId`、`/settings`。
- Python SQLite 是会话、消息、运行、任务、附件和非敏感设置的唯一事实源；Pinia 仅缓存后端快照与实时事件。
- `localStorage` 只保存主题、侧栏折叠等 UI 偏好与旧数据迁移标记，不再保存会话副本。
- 前端领域对象使用 camelCase；所有 wire envelope 和 payload 使用 snake_case。转换只在运行时客户端/Store 边界发生。
- 页面不得直接订阅 Tauri event。单例运行时 Store 只订阅一次 `runtime-event`，再按 `session_id`、`run_id`、`task_id` 合并。
- 运行时断开时允许浏览已加载的历史快照，但禁止提交、停止、重试和确认；恢复后重新请求当前页面数据。

## 路由表

| 路径 | 参数 | 页面职责 | 数据来源 | 空状态与失败行为 |
| --- | --- | --- | --- | --- |
| `/` | 无 | 新建对话（默认项目）；展示空状态、附件和目标输入框 | `runtime.status`、`project.list`、`session.create`、`run.start` | 无历史时显示引导；断线时禁用提交并提供重连/重启入口；创建成功后跳转详情页 |
| `/projects/:projectId` | `projectId: string`，由后端创建 | 项目工作区：发起新对话并浏览项目内对话 | `project.get`、`session.list`、`session.create` | 项目不存在返回“项目不存在”；断线时禁用提交 |
| `/sessions/:sessionId` | `sessionId: string`，由后端创建 | 连续对话、消息流、运行状态、停止/重试、确认门、附件引用、递归委派树与任务详情 | `session.get` 快照及该会话的实时事件 | 不存在返回明确的“会话不存在”；运行失败保留消息与任务，提供重试；运行取消显示终态而非错误 |
| `/settings` | 无 | 主题、Provider、Base URL、模型、API Key 状态、runtime 重启、数据库信息和历史清理 | `settings.get/update`、`runtime.status/restart` | 保存失败保留表单；钥匙串不可用时明确提示；清理历史必须二次确认 |

项目分组、会话列表和委派树属于 `AppShell`，不注册额外页面。侧栏以项目为单位、对话为子结构展示，支持手动收缩为图标栏；小窗口自动折叠，路由和数据行为不变。

## `/`：新建会话

### 提交流程

1. 用户输入目标并选择零个或多个本地附件；附件仅包含用户主动选择的路径与元数据。
2. 调用 `session.create`，以响应中的 `session_id` 为准，不在前端生成持久化 ID。
3. 调用 `run.start`，传入 `session_id`、目标文本和附件引用。
4. 收到成功响应后跳转 `/sessions/{session_id}`。若运行启动失败，会话仍存在，详情页可重试。

附件只接受 Tauri 文件选择器返回的本地路径，不上传、不转为 base64。后端读取 UTF-8 的 Markdown/TXT 并将正文作为不可信参考资料交给 Agent；单文件 1 MiB、合计 2 MiB、最多 4 个。浏览器调试模式显示能力不可用，不伪造路径。

## `/sessions/:sessionId`：连续对话与运行

页面进入时调用 `session.get` 获取完整快照。后续每次提交继续使用同一个 `session_id`，并产生新的 `run_id`；不得再次创建会话。一个会话同一时刻最多一个活动运行，不同会话可并行后台执行。

### 消息和运行

- 用户消息、assistant 流式消息、工具执行、错误和取消状态均来自后端快照或事件。
- `message.created` 建立消息，`message.delta` 按 `message_id` 追加内容，`message.completed` 封存消息。
- `run.cancel` 停止当前运行；终态以 `run.cancelled` 为准。
- `run.retry` 可重试失败运行或指定 `task_id`。后端返回新的 `run_id`，历史运行不可改写。
- Markdown 报告在渲染前必须清理 HTML；工具输出和错误文本按不可信内容处理。

### 递归委派树

任务节点包含 `id`、`parent_id`、`description`、`effort`、`status`、`output` 和 `error`。根任务的 `parent_id` 为 `null`；未知父节点暂挂在根层，后续父节点到达时重新归并。

事件可能乱序或重复，Store 必须执行幂等 upsert：

- 以 `task_id` 定位任务，以 `run_id` 隔离不同运行；
- `task.created` 可晚于 `task.started`，不得丢弃先到事件；
- `task.delta` 只追加到指定任务；
- `completed`、`failed`、`cancelled` 等终态不得被迟到的运行态覆盖；
- 点击树节点滚动定位执行内容，并打开任务详情抽屉；节点可独立折叠。

### 确认门

`approval.requested` 生成内联确认卡片。用户选择后调用 `approval.resolve`，并等待 `approval.resolved` 更新 UI。拒绝和超时都必须是显式结果；未知、已解决或过期的确认请求返回协议错误，前端不得乐观移除。

## `/settings`：设置与维护

### 主题

提供 `system`、`light`、`dark` 三档。主题偏好可保存在 `localStorage`，系统档监听操作系统主题变化；业务数据不进入该存储。

### 模型配置

`settings.get` 返回 Provider、Base URL、模型名和 `api_key_configured`，绝不返回 API Key。`settings.update` 可以携带新 API Key；Rust 将其直接写入系统钥匙串，Python SQLite 只保存非敏感配置。前端不得把 Key 写入 Pinia、日志、事件、异常文本或持久化存储，提交后立即清空输入值。

配置更新需要重启 sidecar 时，页面展示重启过程并重新读取 `runtime.status`，不得乐观显示已连接。

### 数据库与清理

数据库路径、schema 版本和可用状态来自后端只读信息。清理历史通过二次确认后调用后端能力，不直接操作浏览器缓存或 SQLite 文件。

## 侧栏数据行为

- `project.list` 返回项目摘要，`session.list` 返回带 `project_id` 的会话摘要，前端按项目分组展示；不再提供会话搜索。
- 新建项目调用 `project.create`，重命名 `project.rename`，删除 `project.delete`（级联删除项目内对话）并二次确认。
- 新建对话调用 `session.create` 并携带 `project_id`，重命名 `session.rename`，删除 `session.delete` 并二次确认。
- `project.updated` 与 `session.updated` 触发对应 upsert/删除；删除当前会话后导航 `/`。
- 会话运行标记按 `session_id` 更新，因此用户切换页面不会停止后台运行。
- 委派树只展示当前会话当前/选中运行的任务，不混入其他会话事件。

## 旧数据迁移

首次启动若存在 `demo-agent:sessions:v1`：

1. 前端读取原始 payload，生成稳定的 `import_id`，调用幂等的 `session.import_legacy`。
2. Python 在单个 SQLite 事务中校验并导入合法记录，返回 `import_id` 及 `imported`、`skipped`、`failed` 计数。
3. 只有响应 `ok: true` 且 `failed === 0` 时，前端写入迁移完成标记并删除旧 payload。
4. 失败或断线时保留旧 payload，下次启动以同一个 `import_id` 重试；后端导入记录防止重复写入。

迁移过程不得把 API Key、stderr 或运行时配置混入 payload。

## 页面级错误处理

| 场景 | 行为 |
| --- | --- |
| runtime 未就绪/崩溃 | 展示真实状态，禁用写操作，保留历史视图，提供 `runtime.restart` |
| `session_id` 不存在 | 显示不存在状态和返回首页入口，不创建同 ID 的本地空会话 |
| 同会话已有活动运行 | 展示 `RUN_ALREADY_ACTIVE`，定位现有运行，不重复提交 |
| 事件重复/乱序 | Store 依事件 ID 去重并按实体 ID 幂等归并 |
| 文件引用失效 | 保留附件元数据并显示不可访问，不自动扩大文件权限 |
| API Key 保存失败 | 清空表单中的 Key，显示钥匙串错误，不落日志或缓存 |

## 接入检查清单

- 前端发出的每个请求都有唯一 `request_id`，响应只按该 ID 关联。
- 多会话同时运行时，消息、任务和确认均按 `session_id/run_id` 隔离。
- 重新加载详情页后，仅以 `session.get` 恢复，不依赖前端旧缓存。
- 文件对话框只返回用户明确选择的文件。
- 任何日志、Store、SQLite 记录和事件都不包含 API Key。
- 浅色、深色及系统主题下均保持黑白灰主色与少量状态色，无渐变。
