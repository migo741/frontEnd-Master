# 第 10 章练习

## 练习 1：Comparator 驱动的 BinaryHeap（经典机制）

```ts
declare class BinaryHeap<T> {
  constructor(compare: (a: T, b: T) => number, values?: readonly T[]);
  get size(): number;
  peek(): T | undefined;
  push(value: T): void;
  pop(): T | undefined;
}
```

values 用 bottom-up heapify O(n)，不得逐项调用 public push。push/pop O(log n)，peek O(1)，不修改 values。支持重复项和任意一致 comparator。

交付：每次随机操作后检查所有父子不变量，与“数组 sort 后 shift”的慢 oracle 比较。构造 heapify 线性工作量计数实验，与逐项 push 的比较次数对照；不能仅凭一次 wall-clock 宣称复杂度。

## 练习 2：单 timer 过期队列（生产/开放）

实现支持 `schedule(value,deadline)`、`cancel(handle)`、`reschedule(handle,deadline)` 的 `ExpirationQueue<T>`。相同 deadline 按 schedule/reschedule sequence FIFO；十万活跃项始终至多一个底层 timer；lazy stale entry 到堆顶清理，堆膨胀超过 `2*active+64` 时由活跃 handle 重建。

构造函数注入：`now`、`setTimer`、`clearTimer`、`maxDelay`、`maxBatch`、`onExpire`、`onError`。每批最多触发 maxBatch，剩余到期项用 0-delay 继续；callback 异常隔离；callback 内可重入 schedule。handle 跨队列、已取消/到期的操作返回 false。

测试必须使用确定性 fake scheduler，断言任意时刻底层活动 timer<=1；不使用 sleep。覆盖 deadline 已过、相同 deadline、长于 maxDelay、取消最早项、连续重排、callback 抛错/重入、一次到期远超 maxBatch。

发散：进程崩溃怎样恢复？多实例如何避免重复执行？租约、幂等与持久消息队列补的是哪些保证？
