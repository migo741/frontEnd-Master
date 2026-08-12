# 第 13 章练习

## 练习一：不再卡输入的数据分析器

页面每次输入筛选词，都会对一个 `Float64Array`（50 万条）做归一化、过滤和分桶。当前代码在主线程同步运行，输入明显卡顿。

请设计一个 Dedicated Worker 版本：

1. 初始数据只传一次，使用 transferable 移交所有权；
2. 每次查询带递增 `generation`，UI 只接受最新代结果；
3. 新查询到来后取消旧计算，Worker 每 1024 项检查一次；
4. 返回分桶计数和耗时，不返回完整中间数组；
5. 页面卸载时终止 Worker，所有未决 Promise 以 `AbortError` 拒绝。

验收证据：

- 连续输入 20 次，最后结果与同步基准一致；
- Performance 记录显示主线程不再出现由计算产生的持续长任务；
- 记录 clone/transfer、排队、计算、总延迟；
- 测试旧 generation 即使晚到也不会覆盖新结果。

不要先实现池。先证明单 Worker 已解决问题。

## 练习二：有界、可恢复的 Worker 调度器（高难）

实现 `WorkerScheduler` 的协议与核心逻辑：

```js
const scheduler = new WorkerScheduler(workerUrl, {
  size: 3,
  maxQueued: 20,
})

const result = await scheduler.run('hash', payload, {
  priority: 'user-blocking',
  signal,
})
```

约束：

- 任意时刻运行数不超过 `size`；高优先任务先出队，同优先级 FIFO；
- 队列满时拒绝低优先新任务，不得无限增长；
- 每任务有 id，取消排队任务立即拒绝，运行任务发送协作式 cancel；
- Worker 未捕获错误时，只自动重试一次声明为幂等的任务，然后替换该 Worker；
- 旧 Worker 的迟到消息不能完成已经重试的新 Promise；
- `close()` 后拒绝新任务、取消队列、终止所有 Worker。

交付：状态机图、消息 schema、核心实现、至少覆盖并发上限/优先级/取消/崩溃/关闭的测试。复盘说明为什么不能简单用 `Promise.race` 代表 Worker 池。

