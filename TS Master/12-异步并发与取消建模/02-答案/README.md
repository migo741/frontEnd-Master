# 第 12 章参考答案

## 练习一

返回契约可拆两个函数比 overload 更清晰：`mapPool`（fail-fast Promise<U[]>）与 `settlePool`（Promise<Settled<U,E>[]>）。若统一 API：

```ts
type PoolOptions =
  | {mode:'fail-fast'; order:'input'; /*...*/}
  | {mode:'all-settled'; order:'input'|'completion'; /*...*/}

function mapPool<T,U>(inputs: Iterable<T>, worker: Worker<T,U>, options: FailFast): Promise<U[]>
function mapPool<T,U>(inputs: Iterable<T>, worker: Worker<T,U>, options: AllSettled): Promise<Settled<T,U>[]>
```

实现使用 iterator + 固定 N 个 runner，不把 iterable 展开成 100k Promise。共享 next index 在 JS 单线程同步段安全；结果 input-order 存按 index 数组，completion-order push。fail-fast 首错触发内部 controller，组合外部 signal，等待 `Promise.allSettled(runners)` 后 reject/Result，确保 cleanup。

外部 abort listener 放一次并 finally 移除；worker 接 signal。对不合作 worker 只能停止派发/忽略结果，无法强杀。onProgress 包 try/catch，建议 telemetry 回调失败不影响任务但记录；或文档声明传播，二选一。

## 练习二

generator 结构：fetch → reader → TextDecoder → buffer → while newline → parse line。每 append 后检查 buffer byte/char 上限，避免无换行攻击。流结束 `decoder.decode()` flush 并处理剩余非空行。

```ts
try {
  while (true) {
    signal.throwIfAborted()
    const {done, value} = await reader.read()
    if (done) break
    buffer += decoder.decode(value, {stream:true})
    // consume complete lines; yield Result
  }
  buffer += decoder.decode()
  // consume final
  return {events, errors, bytes}
} finally {
  await reader.cancel(signal.reason).catch(() => {})
  reader.releaseLock()
}
```

AsyncGenerator 的 return summary 只有手动迭代读取 done value 才容易取得；`for await` 忽略 return value。若 summary 是核心公共结果，另暴露 Promise/observer，别依赖隐蔽 generator return。

ReadableStream pull 模型下 `await yield/consumer next` 会延缓 reader.read，形成背压；WebSocket push 不等消费者，必须 bounded queue 并定义 drop/coalesce/disconnect。

