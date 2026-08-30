# 第 08 章练习

## 练习 1：lower/upper/equalRange（经典机制）

```ts
type Comparator<T> = (a: T, b: T) => number;

export declare function lowerBound<T>(array: readonly T[], target: T, compare: Comparator<T>): number;
export declare function upperBound<T>(array: readonly T[], target: T, compare: Comparator<T>): number;
export declare function equalRange<T>(array: readonly T[], target: T, compare: Comparator<T>): readonly [number, number];
```

不调用 `findIndex/indexOf`；时间 O(log n)、空间 O(1)；空数组返回 0/[0,0]。写出两个不变量并逐步手算 `[1,2,2,2,5]` 对 target 0、2、4、6。

用线性 oracle 做固定 seed 随机差分；验证边界两侧性质，而不只比较一个样例。另写一个测试展示不一致 comparator 或未排序输入会让结论失效。

## 练习 2：不可变时间序列索引（生产/开放）

```ts
interface TimelineEvent<T> {
  readonly timestamp: number;
  readonly sequence: number;
  readonly payload: T;
}

declare class TimeSeriesIndex<T> {
  constructor(events: readonly TimelineEvent<T>[]);
  eventsBetween(startInclusive: number, endExclusive: number): readonly TimelineEvent<T>[];
  insertionIndex(event: TimelineEvent<T>): number;
  mergeSortedBatch(batch: readonly TimelineEvent<T>[]): TimeSeriesIndex<T>;
}
```

全序为 `(timestamp,sequence)`；timestamp 为有限数，sequence 为非负安全整数，同一复合键不得重复。构造输入和 batch 必须已排序，否则在改变状态前拒绝。查询使用时间半开区间，复杂度 O(log n+k)，不能 filter 全扫；插入位置 O(log n)；批量合并 O(n+m)，不得逐项 splice。

返回数据不得允许调用方修改索引内部顺序。写随机 oracle：线性 filter 查询；`[...old,...batch].sort(compare)` 合并，并检查重复键策略。

发散：相同 timestamp 事件跨页时游标应包含什么？乱序实时事件怎样先进入 delta buffer 再批量归并？亿级数据为何应下推到数据库/分区文件？
