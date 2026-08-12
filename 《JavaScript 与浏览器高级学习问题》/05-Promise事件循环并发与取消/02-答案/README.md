# 第 05 章答案

## 练习 1：事件循环偏序

### 因果链

当前 script 是一个 task，因此所有同步日志先完成：`A → I1 → B`。

`await null` 会安排 async 函数续体；它与 Promise reaction 一样进入 microtask 队列。

当前 task 结束时初始 microtask 顺序为 P1、Q1、I2。

P1 执行时追加 P2，Q1 执行时追加 Q2，所以完整微任务顺序为：

```text
P1 → Q1 → I2 → P2 → Q2
```

注意名称会误导：代码中的 P2 比 Q2 先入队，因为 P1 本身先执行。

合并同步阶段，必定前缀为：

```text
A, I1, B, P1, Q1, I2, P2, Q2
```

Timer 与 MessageChannel 来自不同 task source，本题不应声称 T 与 M 存在跨来源规范总顺序。

若 T 先执行，T 的 task 结束后必须完成 `Tµ`，然后浏览器才会执行另一个 task。

因此尾部可能是 `T, Tµ, M` 或 `M, T, Tµ`，而不是 `T, M, Tµ`。

### 验证伪码

```js
performance.mark("before-case");
// 运行题目代码，每个 log 同时 performance.mark(name)
setTimeout(() => {
  performance.mark("after-case");
  performance.measure("case", "before-case", "after-case");
}, 100);
```

在 Performance 面板查看 Main 线程 task 与 microtask，不把一次 Chrome 实测提升为跨实现保证。

rAF 只在渲染机会前执行；timer 到期、刷新周期、标签页可见性都会影响它与后续 task 的相对位置。

### 复写任务

合上答案，自己画队列变化表；再把 P1 内追加的 queueMicrotask 改为 setTimeout，重新写偏序而非单一序列。

## 练习 2：结构化任务池

### 设计决定

多个 worker 从共享 cursor 领取任务；JavaScript 在两个 await 之间不被抢占，因此领取动作是原子的同步片段。

内部 controller 统一传播“兄弟失败”；外部取消被转发到内部 signal。

所有 worker 都由 Promise.allSettled 结算，之后才返回或抛错，避免孤儿拒绝。

### 可复制实现

```js
function abortError(message = "Aborted") {
  return new DOMException(message, "AbortError");
}

export async function runPool(tasks, options = {}) {
  if (!Array.isArray(tasks) || tasks.some((task) => typeof task !== "function")) {
    throw new TypeError("tasks must be an array of functions");
  }
  const concurrency = options.concurrency ?? 4;
  if (!Number.isInteger(concurrency) || concurrency < 1) {
    throw new RangeError("concurrency must be a positive integer");
  }
  if (tasks.length === 0) return [];

  const external = options.signal;
  const stopOnError = options.stopOnError ?? false;
  const controller = new AbortController();
  let hasExternalAbort = false;
  let externalReason;
  let hasFailure = false;
  let firstFailure;

  const onExternalAbort = () => {
    hasExternalAbort = true;
    // 不使用 ??：abort(null) 的 null 是调用方明确给出的 reason，必须原样传播。
    externalReason = "reason" in external ? external.reason : abortError();
    if (!controller.signal.aborted) controller.abort(externalReason);
  };

  if (external?.aborted) onExternalAbort();
  else external?.addEventListener("abort", onExternalAbort, { once: true });

  const results = new Array(tasks.length);
  let cursor = 0;

  async function worker() {
    while (true) {
      if (controller.signal.aborted) return;
      const index = cursor;
      if (index >= tasks.length) return;
      cursor += 1;

      try {
        const value = await tasks[index](controller.signal, index);
        results[index] = { status: "fulfilled", value };
      } catch (reason) {
        results[index] = { status: "rejected", reason };
        if (stopOnError && !hasFailure && !hasExternalAbort) {
          hasFailure = true;
          firstFailure = reason;
          controller.abort(reason);
        }
      }
    }
  }

  try {
    const workerCount = Math.min(concurrency, tasks.length);
    await Promise.allSettled(Array.from({ length: workerCount }, worker));
  } finally {
    external?.removeEventListener("abort", onExternalAbort);
  }

  if (hasExternalAbort) throw externalReason;
  if (hasFailure) throw firstFailure;
  return results;
}
```

### 测试要点

为每个 task 在开始时 `active++`、finally 中 `active--`，持续记录 maxActive，断言不超限。

创建 deferred 数组，按 3、1、2、0 的顺序 resolve，结果仍按 0、1、2、3 排列。

stopOnError false 时混合同步 throw、reject、普通值和 thenable，断言都出现在对应 allSettled 槽位。

stopOnError true 时让第一个 worker 失败，断言失败后没有领取新索引，并让已启动任务监听 abort 后结束。

分别让 task 执行 `throw undefined` 与返回 `Promise.reject()`；两者都必须触发停止调度，最终 Promise 必须以 undefined 拒绝。

外部取消应以外部 reason 为最终错误，即使任务因同一 signal 拒绝。

执行 `controller.abort(null)`，断言 runPool 最终以严格相等的 null 拒绝，不能被默认 AbortError 替换。

在测试结束附加一次事件循环 tick，并监听 unhandledrejection，确认没有漏接拒绝。

### 边界

协作取消无法强制终止忽略 signal 且永不 settled 的 task；结构化作用域会等待它。

这是有意的安全边界。若要隔离不可信 CPU 任务，应放入 Worker，并由所有者 terminate。

本实现把“第一个观察到的业务失败”作为抛出值；若需完整报告，可收集 AggregateError。

### 复写任务

合上答案重写；再增加每任务 timeout，但必须把 timeout signal 与池 signal 合并，且正确清理监听器。
