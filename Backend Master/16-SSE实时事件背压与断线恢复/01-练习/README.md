# 第 16 章练习

规则：先写事件协议、失败表和验收测试，再写实现。两题都基于毕业项目的 `agent_run`，不要另造一次性 Demo。

## 练习一：可断点续传的 SSE 工单流

实现：

```http
GET /api/runs/:runId/events
Last-Event-ID: 41
Accept: text/event-stream
```

服务端从 PostgreSQL 回放 `seq > 41` 的事件，然后进入实时订阅。

约束：

- run 必须同时按可信 `tenantId` 与 `runId` 查询；
- 返回正确 SSE headers，并每 15 秒写一次注释心跳；
- 每帧都有 `id/event/data`；
- 数据库回放和实时订阅交界处允许重复，但输出不得重复；
- `response.write()` 返回 `false` 时等待 `drain`；
- 客户端断开只释放订阅，不取消 run；
- `run.succeeded/run.failed/run.cancelled` 发出后正常结束流；
- 非法 `Last-Event-ID` 返回 `400`，无权限统一返回 `404`；
- 单连接有 30 分钟截止时间和最大积压限制。

必须提交的测试：

1. 从 0 完整回放；
2. 从中间序号恢复；
3. 回放/订阅竞态产生重复但只发送一次；
4. 慢消费者触发背压；
5. 断连后业务 run 仍继续；
6. 跨租户无法观察 run。

证据：保存一次 `curl -N` 输出、一次断网重连时间线和背压测试结果。

## 练习二：可恢复的 Agent 事件协议

为以下事件建立版本化判别联合和服务端状态规约：

```text
run.started
run.token
run.step
tool.proposed
tool.approval_required
tool.completed
run.failed
run.succeeded
run.cancelled
```

实现一个 reducer/投影器，把持久事件还原为客户端可用快照。

约束：

- 事件包含 `version/runId/seq/occurredAt/type/payload`；
- 只接受连续序号；缺口返回 `needs_snapshot`，不能猜测；
- 重复序号且内容一致时忽略，内容冲突时报告协议损坏；
- terminal 后拒绝任何非重复事件；
- token 可批量合并，tool、approval、error 与 terminal 不得丢弃；
- 显式取消走独立、幂等的 `POST /runs/:id/cancel`；
- 断开连接与取消不得共用同一个 AbortController；
- 未知主版本触发全量快照，不默默忽略。

测试至少覆盖重复、缺口、乱序、终态后迟到、取消竞态以及旧版客户端。

最后写 300 字设计说明：为什么“直接把模型 SDK stream pipe 到响应”无法满足这些不变量。
