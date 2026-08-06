# 第 10 章练习

## 练习一：Schema 驱动 Fetch SDK

实现：

```ts
const user = await client.get('/users/:id', {
  params: {id: userId},
  query: {include: ['roles']},
  response: UserSchema,
  signal,
})
```

要求：

- path params 完整、URL encode；query 对 array/null/undefined 有规范。
- response T 只从 Schema output 推断；不允许自选泛型。
- 检查 status/content-type/204；HTTP/Network/Decode/Abort 错误判别。
- 响应错误带 requestId/path issues，日志脱敏。
- request body 也经 Schema/encoder；unknown keys 策略明确。
- 超时与用户 AbortSignal 组合但不泄漏 timer。
- MSW/假 server 测试坏 JSON、坏 shape、巨大 payload、401/422/500。

## 练习二：版本化离线事件迁移（高难）

IndexedDB 保存：

```ts
{schemaVersion: 1|2|3, type: string, payload: unknown, createdAt: string}
```

要求：

- v1/v2 各自 Schema，逐步 migrate 到当前 v3 Domain；不让历史 union 进入业务层。
- migration 幂等/可重跑，失败隔离单条并保留恢复证据。
- future version 不删除，标记 unsupported；未知 type 策略明确。
- 批量 100k 条有内存/时间预算和进度/取消。
- migration 版本分布可观测；删除旧迁移器有门槛。
- property/fixture tests 防数据丢失，敏感字段在 v2→v3 被 strip。

