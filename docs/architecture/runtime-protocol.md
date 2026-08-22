# Agent Runtime 协议 v1

本文是 Nuxt 前端、Tauri Rust broker、Python stdio/WebSocket transport 之间的公共 wire 契约。所有传输必须具有相同语义；新增字段应保持向后兼容，破坏性变更必须提升 `protocol_version`。

## 编码与命名

- 协议版本：`1`。
- stdio：UTF-8 NDJSON，一行一个完整 JSON 对象；业务日志只能写 stderr。
- WebSocket：UTF-8 JSON text frame，一帧一个完整 JSON 对象。
- wire 字段统一 snake_case；前端 UI 领域对象在 Store 边界转换为 camelCase。
- 时间使用 UTC RFC 3339 字符串；ID 为不透明字符串，前端不得解析其前缀。
- 可选字段可以省略；显式 `null` 仅用于本文声明可空的字段。

## Envelope

### 请求

```json
{
  "protocol_version": 1,
  "request_id": "req_01H...",
  "method": "session.list",
  "params": {}
}
```

`request_id` 在一个客户端连接生命周期内唯一。broker 与 Python 都必须原样回传，不能依请求到达顺序关联响应。

### 成功响应

```json
{
  "protocol_version": 1,
  "request_id": "req_01H...",
  "ok": true,
  "result": {}
}
```

### 失败响应

```json
{
  "protocol_version": 1,
  "request_id": "req_01H...",
  "ok": false,
  "error": {
    "code": "SESSION_NOT_FOUND",
    "message": "Session does not exist",
    "details": {}
  }
}
```

错误 `message` 面向用户但不得含密钥、完整提示词、文件内容或内部 traceback；诊断信息写 stderr 并同样脱敏。常用错误码：

| code | 含义 |
| --- | --- |
| `INVALID_REQUEST` | envelope、方法或参数不合法 |
| `PROTOCOL_VERSION_UNSUPPORTED` | 不支持所请求的协议版本 |
| `SESSION_NOT_FOUND` | 会话不存在 |
| `RUN_NOT_FOUND` | 运行不存在 |
| `RUN_ALREADY_ACTIVE` | 同一会话已有活动运行 |
| `TASK_NOT_FOUND` | 指定任务不存在或不属于该运行 |
| `APPROVAL_NOT_FOUND` | 确认请求不存在、已解决或已过期 |
| `RUNTIME_UNAVAILABLE` | sidecar 未就绪或正在重启 |
| `KEYRING_UNAVAILABLE` | 系统钥匙串不可用 |
| `INTERNAL_ERROR` | 已脱敏的内部错误 |

### 事件

```json
{
  "protocol_version": 1,
  "event_id": "evt_01H...",
  "type": "task.started",
  "occurred_at": "2026-08-22T03:12:45.123Z",
  "session_id": "ses_01H...",
  "run_id": "run_01H...",
  "payload": {
    "task_id": "task_01H..."
  }
}
```

`session_id` 和 `run_id` 按事件类型可选，但所有会话、运行、任务、消息和确认事件必须带足够的归并 ID。消费者以 `event_id` 去重，以实体 ID 幂等 upsert；不得依赖事件顺序。

## 核心实体

### Session

```ts
interface SessionWire {
  id: string
  title: string
  created_at: string
  updated_at: string
  active_run_id?: string | null
}
```

### Message

```ts
interface MessageWire {
  id: string
  session_id: string
  run_id?: string | null
  role: 'user' | 'assistant' | 'tool' | 'system'
  kind: 'text' | 'report' | 'tool' | 'error'
  content: string
  status: 'streaming' | 'completed' | 'failed' | 'cancelled'
  created_at: string
  updated_at: string
}
```

### Run

```ts
interface RunWire {
  id: string
  session_id: string
  objective: string
  status: 'queued' | 'running' | 'waiting' | 'completed' | 'failed' | 'cancelled'
  retry_of_run_id?: string | null
  retry_task_id?: string | null
  error?: string | null
  created_at: string
  started_at?: string | null
  completed_at?: string | null
}
```

### Task

```ts
interface TaskWire {
  id: string
  run_id: string
  parent_id: string | null
  description: string
  effort: 'low' | 'medium' | 'high'
  status: 'queued' | 'running' | 'waiting' | 'completed' | 'failed' | 'cancelled'
  output: string
  error: string | null
  created_at: string
  updated_at: string
}
```

### Attachment

```ts
interface AttachmentWire {
  id: string
  session_id: string
  run_id?: string | null
  path: string
  name: string
  size?: number | null
  media_type?: string | null
}
```

附件是本地引用，不表示 runtime 已读取或上传文件。只有 Tauri 文件选择器返回且用户确认的路径可以进入协议。

## 请求方法

方法名称是稳定公共 API。下表给出最小参数与结果；实现可增加可选字段。

| method | params | result | 语义 |
| --- | --- | --- | --- |
| `runtime.status` | `{}` | `{ status, mode, model, database, protocol_version }` | 返回 broker/runtime 的真实状态，不能乐观伪造 ready |
| `runtime.restart` | `{}` | `{ accepted: true }` | 安全终止并重启 sidecar；过程中发 runtime 事件 |
| `session.list` | `{ query?, limit?, cursor? }` | `{ sessions, next_cursor? }` | 按 `updated_at` 降序列出摘要 |
| `session.create` | `{ title? }` | `{ session }` | 创建空会话 |
| `session.get` | `{ session_id }` | `{ session, messages, runs, tasks, attachments, approvals }` | 返回可完整恢复页面的快照 |
| `session.rename` | `{ session_id, title }` | `{ session }` | 重命名并更新 `updated_at` |
| `session.delete` | `{ session_id }` | `{ deleted: true }` | 事务删除会话及关联实体；活动运行时拒绝或先显式取消 |
| `session.import_legacy` | `{ import_id, sessions }` | `{ import_id, imported, skipped, failed, failures }` | 幂等、单事务导入旧浏览器记录 |
| `run.start` | `{ session_id, objective, attachments? }` | `{ run }` | 在已有会话追加用户消息并启动运行 |
| `run.cancel` | `{ session_id, run_id }` | `{ accepted: true }` | 设置取消令牌；以终态事件为准 |
| `run.retry` | `{ session_id, run_id, task_id? }` | `{ run }` | 创建新运行重试失败运行或指定任务 |
| `approval.resolve` | `{ session_id, run_id, approval_id, approved }` | `{ accepted: true }` | 解决待确认操作，幂等重复需返回当前结果或明确错误 |
| `settings.get` | `{}` | `{ provider, base_url, model, api_key_configured }` | 不返回 Key 本身 |
| `settings.update` | `{ provider, base_url, model, api_key? }` | `{ provider, base_url, model, api_key_configured, restart_required }` | 非敏感项写 SQLite，Key 由 Rust 写系统钥匙串 |

### 并发语义

- Run Manager 对每个 `session_id` 持有活动运行锁；同一会话最多一个 `queued/running/waiting` 运行。
- 不同会话拥有独立锁和取消令牌，可以并行执行。
- `run.cancel` 是请求取消，不是立即成功终态；释放会话锁前必须持久化 `cancelled` 并发出事件。
- `run.retry` 总是创建新 `run_id`，通过 `retry_of_run_id`/`retry_task_id` 保留来源。
- 崩溃恢复时，无法继续的活动运行应原子标为失败或取消，不能永久占锁。

## 事件目录

所有事件的 `payload` 只包含业务数据，不包含 API Key 或密钥摘要之外的信息。

| type | 必需关联字段 | payload 最小字段 | 语义 |
| --- | --- | --- | --- |
| `runtime.ready` | 无 | `{ mode, model, protocol_version }` | Python 初始化、迁移与 transport 就绪 |
| `runtime.disconnected` | 无 | `{ reason, recoverable }` | sidecar 退出、管道关闭或重启中 |
| `session.updated` | `session_id` | `{ session }` | 创建、重命名、消息或运行导致摘要变化 |
| `run.started` | `session_id`, `run_id` | `{ run }` | 运行取得会话锁并开始 |
| `run.completed` | `session_id`, `run_id` | `{ run }` | 报告与消息已持久化 |
| `run.cancelled` | `session_id`, `run_id` | `{ run }` | 取消终态已持久化并释放锁 |
| `run.failed` | `session_id`, `run_id` | `{ run, error }` | 失败终态已持久化并释放锁 |
| `plan.created` | `session_id`, `run_id` | `{ tasks }` | 首批计划任务；后续递归委派使用 `task.created` |
| `task.created` | `session_id`, `run_id` | `{ task }` | 创建任意深度任务 |
| `task.started` | `session_id`, `run_id` | `{ task_id }` | 任务进入 running |
| `task.delta` | `session_id`, `run_id` | `{ task_id, delta }` | 向指定任务输出追加文本 |
| `task.completed` | `session_id`, `run_id` | `{ task }` | 任务完成，含最终 output |
| `task.failed` | `session_id`, `run_id` | `{ task, error }` | 任务失败 |
| `approval.requested` | `session_id`, `run_id` | `{ approval_id, task_id?, action, risk, expires_at }` | 运行等待用户确认 |
| `approval.resolved` | `session_id`, `run_id` | `{ approval_id, approved, resolved_at, resolution }` | 已批准、拒绝或超时 |
| `message.created` | `session_id`, `run_id?` | `{ message }` | 创建消息记录 |
| `message.delta` | `session_id`, `run_id?` | `{ message_id, delta }` | 追加流式内容 |
| `message.completed` | `session_id`, `run_id?` | `{ message }` | 消息终态持久化 |

`plan.created.tasks` 和 `task.created.task` 均使用完整 `TaskWire`。如果事件乱序，客户端先创建占位实体，随后以完整实体补齐。

## Tauri broker 映射

前端通过一个通用 Tauri command 提交请求 envelope；Rust 按 `request_id` 建立 pending map，将 NDJSON response 返回给正确的 invoke，将 event 作为全局 `runtime-event` 广播。具体 Rust command 名可视实现注册，但不得为每个业务方法重新定义不一致的 payload。

Rust broker 负责：

1. 启动、停止、重启、崩溃检测与有限退避恢复；
2. NDJSON 分帧、请求关联、超时和 pending request 失败回收；
3. 缓存并返回真实 runtime 状态；
4. 将 API Key 写入/读取系统钥匙串，仅把是否已配置暴露给前端；
5. 打开系统文件选择器，只转交用户选择的路径和元数据；
6. 对 stdout 协议帧与 stderr 日志脱敏，不打印请求中的 `api_key`。

Python transport 负责协议校验和业务方法分派。stdio 与 WebSocket 必须共用同一个 dispatcher、同一套 envelope model 和错误码，测试应对相同请求断言等价响应/事件。

## 持久化与事务

Python SQLite 启用 foreign keys、WAL 和版本化迁移，至少持久化 sessions、messages、runs、tasks、attachments、approvals、非敏感 settings 和 legacy import 记录。

- 创建消息/运行/任务及对应状态变更在事务内提交后才发事件。
- 事件是变更通知，不是事实源；断线或漏事件后使用 `session.get` 重建。
- `session.import_legacy` 以 `import_id` 幂等。所有合法导入写入与 import 记录处于同一事务；发生数据库异常时整体回滚。
- 业务级无效记录可计入 `failed/failures`，但前端只有在 `failed === 0` 时删除旧 payload。
- SQLite 禁止保存 API Key；模型 provider/base URL/model 可保存。

## 扩展端口与占位规则

应用层依赖以下端口而不是直接依赖生产 SDK：

- `ModelPort`：规划、worker 与报告模型调用；
- `McpPort`：MCP 工具发现与调用；
- `KvCachePort`：可选缓存/能力特化接入；
- `DocumentParserPort`：附件解析。

抽象方法可用 `pass` 表示接口，尚未实现的生产适配器必须明确抛出 `NotImplementedError`。确定性 Mock planner/worker 必须可运行，使无密钥模式覆盖完整 UI 流程。SQLite、transport、请求关联、确认门、取消、迁移和安全路径不得静默占位。

## 兼容性与安全检查

- 未知 method 返回 `INVALID_REQUEST`，不能让 transport 崩溃。
- 未知事件字段应忽略；未知事件类型应记录脱敏警告并继续连接。
- API Key 不进入 response、event、SQLite、Pinia、localStorage、运行状态、任务输出或日志。
- 路径只来源于文件选择器；Python 不因收到路径自动获取父目录或通配范围权限。
- 错误响应与崩溃恢复必须使所有 pending request 结束，不能无限悬挂。
- 每次协议变更同时更新本文、[桌面架构](desktop.md)和[前端路由](frontend-routes.md)。
