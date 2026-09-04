// 要求：5 9 10 11 14 15 17 18
// React 1-7 10 11 01 04练习二 16章可以砍
// AI Agent 1 2 3 4 6 8 9 10 12 17 19

// 1. 同时运行数永不超过 concurrency，结果按输入位置排列。
// 2. `stopOnError:false` 返回 allSettled 形状，所有任务均被观察。
// 3. `stopOnError:true` 首个业务失败后停止启动新任务，取消已启动兄弟，结算后抛原始错误。
// 4. 外部 signal 取消后停止启动，向在途任务传播，结算后抛 `signal.reason`。
// 5. task 同步抛错、返回 thenable、空数组、非法并发数都要覆盖。
// 6. 不得产生 unhandled rejection；说明任务若忽略 signal 时的限制。

// 用可控 deferred Promise 证明上限、保序和每一种完成排列。

await runPool(taskFunctions, {
  concurrency: 4,
  signal,
  stopOnError: false,
})

// 每个 task 是 `(signal, index) => value | Promise<value>`。
