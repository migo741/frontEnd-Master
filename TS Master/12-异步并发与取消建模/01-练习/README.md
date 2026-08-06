# 第 12 章练习

## 练习一：类型安全并发任务池

实现：

```ts
mapPool(inputs, worker, {
  concurrency: 5,
  mode: 'all-settled' | 'fail-fast',
  order: 'input' | 'completion',
  signal,
  onProgress,
})
```

要求：

- overload/判别 options 让不同 mode 返回正确类型；不使用调用者自选泛型。
- concurrency 1..100 runtime 校验；不提前创建全部 Promise。
- fail-fast abort 其余合作任务并等待 cleanup；all-settled 保留每项 input/index。
- signal 开始前/运行中/排队时都生效；无 listener 泄漏。
- worker 同步 throw/async reject 统一处理；onProgress 错误不破坏池或策略明确。
- 测最大同时数、顺序、取消、空数组、10 万输入内存。

## 练习二：可取消 NDJSON AsyncIterable（高难）

把 fetch ReadableStream 转为：

```ts
AsyncGenerator<Result<Event, DecodeError>, StreamSummary, void>
```

要求：

- UTF-8 半字符、一行跨 chunk、多行同 chunk、末尾无换行。
- 每行 JSON 从 unknown 经 Schema；坏行可 yield error 后继续（可配置 fail-fast）。
- 最大行长/总事件/空行策略；防无限 buffer。
- consumer break、abort、网络错误时 reader.cancel/releaseLock，summary 语义明确。
- sequence 缺口/重复在更高协议层处理，不塞进通用 parser。
- 测慢 consumer 是否自然背压，以及 WebSocket push 为何不同。

