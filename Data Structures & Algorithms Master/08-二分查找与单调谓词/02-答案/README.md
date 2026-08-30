# 第 08 章参考答案

## 题 1

```ts
export type Comparator<T> = (a: T, b: T) => number;

export function lowerBound<T>(
  array: readonly T[], target: T, compare: Comparator<T>,
): number {
  let lo = 0, hi = array.length;
  while (lo < hi) {
    const mid = lo + Math.floor((hi - lo) / 2);
    if (compare(array[mid]!, target) < 0) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

export function upperBound<T>(
  array: readonly T[], target: T, compare: Comparator<T>,
): number {
  let lo = 0, hi = array.length;
  while (lo < hi) {
    const mid = lo + Math.floor((hi - lo) / 2);
    if (compare(array[mid]!, target) <= 0) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

export function equalRange<T>(
  array: readonly T[], target: T, compare: Comparator<T>,
): readonly [number, number] {
  return [lowerBound(array, target, compare), upperBound(array, target, compare)];
}
```

lower 的不变量是 `[0,lo)` 全部 `< target`，`[hi,n)` 全部 `>= target`；upper 把两侧改为 `<=` 与 `>`。每轮保留可能边界且区间长度下降。终止 lo=hi 时，左边全部不满足、右边全部满足，因此该点是 first true。

比较器调用 O(log n)，空间 O(1)。若比较一次不是 O(1)，总成本是 O(log n × compareCost)。

线性 oracle：从 0 起找第一个 `compare(x,target)>=0`，没有返回 n；upper 类似 `>0`。随机生成数组后先用同一 compare 排序，再比较。还要直接断言所有 `[0,result)` 与 `[result,n)` 的关系，避免 oracle 和被测代码共享同一种边界错误。

## 题 2

### 1. 用复合哨兵找时间边界

`eventsBetween(start,end)` 的左边界是第一个 `(timestamp,sequence) >= (start, -∞)`；右边界是第一个 `>= (end,-∞)`。由于合法 sequence 非负，可用 -1 作为边界哨兵，但更清晰的实现直接按 timestamp 写专用 first-timestamp 二分。

```ts
export interface TimelineEvent<T> {
  readonly timestamp: number;
  readonly sequence: number;
  readonly payload: T;
}

function compareKey<T>(a: TimelineEvent<T>, b: TimelineEvent<T>): number {
  if (a.timestamp !== b.timestamp) return a.timestamp < b.timestamp ? -1 : 1;
  return a.sequence < b.sequence ? -1 : a.sequence > b.sequence ? 1 : 0;
}

function validateEvent<T>(event: TimelineEvent<T>): void {
  if (!Number.isFinite(event.timestamp)) throw new RangeError("timestamp must be finite");
  if (!Number.isSafeInteger(event.sequence) || event.sequence < 0) throw new RangeError("bad sequence");
}

function firstTimestamp<T>(events: readonly TimelineEvent<T>[], timestamp: number): number {
  let lo = 0, hi = events.length;
  while (lo < hi) {
    const mid = lo + Math.floor((hi - lo) / 2);
    if (events[mid]!.timestamp < timestamp) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

export class TimeSeriesIndex<T> {
  readonly #events: readonly TimelineEvent<T>[];

  constructor(events: readonly TimelineEvent<T>[]) {
    const copy = events.map((event) => {
      validateEvent(event);
      return Object.freeze({ ...event });
    });
    for (let i = 1; i < copy.length; i += 1) {
      if (compareKey(copy[i - 1]!, copy[i]!) >= 0) {
        throw new Error(`events must be strictly sorted; violation at ${i}`);
      }
    }
    this.#events = Object.freeze(copy);
  }

  eventsBetween(startInclusive: number, endExclusive: number): readonly TimelineEvent<T>[] {
    if (!Number.isFinite(startInclusive) || !Number.isFinite(endExclusive) || startInclusive > endExclusive) {
      throw new RangeError("invalid time range");
    }
    const lo = firstTimestamp(this.#events, startInclusive);
    const hi = firstTimestamp(this.#events, endExclusive);
    return Object.freeze(this.#events.slice(lo, hi));
  }

  insertionIndex(event: TimelineEvent<T>): number {
    validateEvent(event);
    return lowerBound(this.#events, event, compareKey);
  }

  mergeSortedBatch(batch: readonly TimelineEvent<T>[]): TimeSeriesIndex<T> {
    const incoming = batch.map((event) => { validateEvent(event); return Object.freeze({ ...event }); });
    for (let i = 1; i < incoming.length; i += 1) {
      if (compareKey(incoming[i - 1]!, incoming[i]!) >= 0) throw new Error(`batch not strictly sorted at ${i}`);
    }

    const merged: TimelineEvent<T>[] = [];
    let i = 0, j = 0;
    while (i < this.#events.length && j < incoming.length) {
      const relation = compareKey(this.#events[i]!, incoming[j]!);
      if (relation === 0) throw new Error("duplicate timeline key across snapshot and batch");
      if (relation < 0) merged.push(this.#events[i++]!);
      else merged.push(incoming[j++]!);
    }
    while (i < this.#events.length) merged.push(this.#events[i++]!);
    while (j < incoming.length) merged.push(incoming[j++]!);
    return new TimeSeriesIndex(merged);
  }
}
```

### 2. 正确性、成本与快照语义

构造器确保数组按复合键严格递增，所以同键重复被拒绝。firstTimestamp 的不变量使 lo/hi 精确夹住 `[start,end)`；slice 只复制 k 个结果。查询 O(log n+k)，insertionIndex O(log n)，merge 每轮至少推进 i/j 之一，所以 O(n+m)，新快照空间 O(n+m)。构造新实例会再次验证 O(n+m)，保持防御性但有重复扫描；可用私有已验证构造器优化，前提测试覆盖。

`Object.freeze` 是浅冻结；payload 若为可变对象仍可被外部修改，但不会改变索引键。若 payload 也需不可变，应由领域层使用不可变值/深复制，而不是对任意图盲目深冻。

### 3. 生产边界

返回 slice 避免暴露内部数组，但超大结果仍会分配；生产查询应分页/流式。游标至少包含 timestamp 与 sequence，只有 timestamp 会在同刻事件处重复/跳过。实时乱序流可先进入有界 delta，达到批次/时间阈值后排序并 O(n+m) 归并；必须定义最大迟到与背压。

亿级持久数据应使用数据库 B-tree/BRIN、列式文件和分区裁剪，不应复制进一个 JS 数组。本类是不可变内存快照算法，不处理持久化、并发发布和版本回收。

复写任务：增加 `pageAfter(cursor,limit)`，游标为完整复合键；用 upperBound 保证上一页末项不重复。再写一个只含 timestamp 的错误游标，用三个同刻事件演示漏项。

