# 第 17 章练习

两题都禁止让 Python 直连业务 PostgreSQL，也禁止把用户 Cookie、JWT 或数据库 DSN 放进消息。

## 练习一：可演进的 Node ↔ Python Agent 契约

设计并实现 `AgentJobV1` 与 `AgentResultV1`：

```text
Node -- durable queue --> Python worker
Node <-- durable result -- Python worker
```

任务至少包含 `schemaVersion/messageId/runId/tenantId/attempt/deadline/inputRef/inputSha256/capabilities/traceparent`。

结果只能是判别联合：

- `completed`：结构化 result、usage、checkpoint；
- `tool_intent`：白名单工具与 JSON 参数；
- `retryable_error`：稳定 code 与建议 retryAfter；
- `permanent_error`：稳定 code；
- `cancelled`：最后安全 checkpoint。

约束：

- TypeScript 与 Pydantic 都使用 `extra = forbid`；
- 时间必须为带时区 ISO 8601，deadline 已过则不调用模型；
- input 通过短时对象引用读取并校验 SHA-256；
- capability 只能来自枚举且绑定资源；
- 未知主版本进入 quarantine/DLQ；
- 共享不少于 8 个有效/无效 JSON fixtures；
- 测试旧 worker 接收新增可选字段，以及新 worker 读取旧任务；
- trace 字段错误不能破坏任务，但不得传播任意 baggage。

提交 JSON Schema、TS parser、Pydantic model、双向 fixture 测试和版本发布顺序说明。

## 练习二：参数绑定的 Tool Intent 与 HITL

实现以下持久状态机：

```text
proposed → awaiting_approval → approved → executing → succeeded
                    └───────→ rejected
                    └───────→ expired
                                  executing → failed_retryable
                                  executing → failed_permanent
```

选择一个真实副作用，例如：关闭工单、发送外部邮件或扣减 Agent 额度。

约束：

- Python 只提交 `{intentId, tool, args}`；
- Node 对 args 做 Schema、租户、资源、业务状态与权限校验；
- 审批绑定 `intentId + tenantId + canonicalArgsHash + expiresAt`；
- 审批页面展示精确资源与影响，不能只显示工具名；
- 执行前重新授权并校验 hash、过期、状态和工具开关；
- `intentId` 是外部调用幂等键；
- 两个执行器竞争时只能一个拿到 lease；
- 审批后参数被替换、成员被移除、重复消息和进程崩溃都要测试；
- 所有状态变化写入 append-only audit log。

证据：提交状态转换表、并发测试、一次拒绝记录和一次“执行后崩溃再恢复但未重复副作用”的时间线。
