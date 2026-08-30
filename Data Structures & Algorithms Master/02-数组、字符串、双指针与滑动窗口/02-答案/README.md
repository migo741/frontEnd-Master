# 第 02 章答案

## 练习 1：稳定原地去重

### 思路与不变量

`read` 扫描原数组，`write` 表示有效前缀长度。每轮开始时：

- `[0, write)` 是已扫描前缀正确、稳定的去重结果。
- `values[write - 1]`（若存在）是最后一个已保留分组的第一条记录。
- `[read, values.length)` 尚未处理。

排序前提保证相同项连续，因此当前项只需与“最后一个保留项”比较。不同则写到 `values[write]` 并增加 `write`；相同则跳过。

```text
有效且已去重          已扫描但可废弃      未扫描
[0 ........ write) [write ........ read) [read .... n)
```

初始化时空数组直接返回；非空数组先把第一项视为已保留，故 `write = 1`、`read = 1`。终止时所有输入都被归类，有效前缀就是完整答案。

### 参考 TypeScript 实现

```ts
export function uniqueSortedInPlace<T>(
  values: T[],
  isSame: (a: T, b: T) => boolean,
): number {
  if (values.length === 0) return 0;

  let write = 1;

  for (let read = 1; read < values.length; read += 1) {
    if (!isSame(values[write - 1]!, values[read]!)) {
      values[write] = values[read]!;
      write += 1;
    }
  }

  return write;
}
```

### 复杂度

- 时间：`O(n)`。
- 辅助空间：`O(1)`。
- 会修改输入数组的前缀；尾部槽位内容未定义为结果。

### 测试

```ts
import assert from "node:assert/strict";
import test from "node:test";
import { uniqueSortedInPlace } from "./uniqueSortedInPlace.js";

const sameNumber = (a: number, b: number) => a === b;

test("handles empty, equal and distinct arrays", () => {
  const empty: number[] = [];
  assert.equal(uniqueSortedInPlace(empty, sameNumber), 0);

  const equal = [2, 2, 2];
  const equalLength = uniqueSortedInPlace(equal, sameNumber);
  assert.deepEqual(equal.slice(0, equalLength), [2]);

  const distinct = [1, 2, 3];
  const distinctLength = uniqueSortedInPlace(distinct, sameNumber);
  assert.deepEqual(distinct.slice(0, distinctLength), [1, 2, 3]);
});

test("keeps the first object in each id group", () => {
  const first = { id: 1, value: "first" };
  const duplicate = { id: 1, value: "later" };
  const second = { id: 2, value: "second" };
  const rows = [first, duplicate, second];

  const length = uniqueSortedInPlace(rows, (a, b) => a.id === b.id);
  assert.deepEqual(rows.slice(0, length), [first, second]);
  assert.equal(rows[0], first);
});
```

### 失败边界

- 相同项不相邻时，本算法不会全局去重。
- `isSame` 若不满足等价关系，结果不可预测。
- 尾部仍可能持有被移除对象的引用；若释放引用很重要，可在调用处设置 `values.length = newLength`，但这会改变数组长度。
- 原地写入会影响所有共享该数组引用的调用方，包括 Vue 响应式消费者。

### 生产替代方案

- 不允许 mutation 时，返回新数组的简单线性实现通常更符合状态管理约定。
- 数据未排序且必须保持首次出现顺序时，使用 `Set`/`Map` 做 `O(n)` 期望时间去重。
- 数据来自数据库时，优先让查询层通过唯一索引或明确的分组规则去重。

## 练习 2：定位请求峰值时间窗

### 思路与不变量

让 `right` 依次加入事件。只要两端时间差 `>= windowMs`，就推进 `left`，直到窗口重新合法。

更新答案前维持：

- `[left, right]` 内所有事件都能放入以 `timestamps[left]` 开始的半开时间窗。
- 若 `left > 0` 且刚发生过收缩，则更靠左的事件不能与当前 `right` 共存。
- `left`、`right` 都只向右移动。

当前事件数是 `right - left + 1`，对应下标半开区间 `[left, right + 1)`。只在数量严格变大时更新，便自然保留最早的平局窗口。

### 参考 TypeScript 实现

```ts
export interface PeakWindow {
  from: number;
  toExclusive: number;
  count: number;
}

function validateInput(
  timestamps: readonly number[],
  windowMs: number,
): void {
  if (!Number.isSafeInteger(windowMs) || windowMs <= 0) {
    throw new RangeError("windowMs must be a positive safe integer");
  }

  for (let index = 0; index < timestamps.length; index += 1) {
    const timestamp = timestamps[index]!;
    if (!Number.isSafeInteger(timestamp)) {
      throw new TypeError(`timestamps[${index}] must be a safe integer`);
    }
    if (index > 0 && timestamps[index - 1]! > timestamp) {
      throw new RangeError("timestamps must be sorted in non-decreasing order");
    }
  }
}

export function findPeakRequestWindow(
  timestamps: readonly number[],
  windowMs: number,
): PeakWindow | null {
  validateInput(timestamps, windowMs);
  if (timestamps.length === 0) return null;

  let left = 0;
  let best: PeakWindow = { from: 0, toExclusive: 1, count: 1 };

  for (let right = 0; right < timestamps.length; right += 1) {
    while (timestamps[right]! - timestamps[left]! >= windowMs) {
      left += 1;
    }

    const count = right - left + 1;
    if (count > best.count) {
      best = { from: left, toExclusive: right + 1, count };
    }
  }

  return best;
}
```

这里使用差值而不是 `timestamps[left] + windowMs`，避免右端点相加越过安全整数范围。若时间域可能跨越极端正负安全整数，数据入口应进一步约束时间范围或改用 `bigint`。

### 复杂度

- 输入验证 `O(n)`，窗口扫描 `O(n)`，合计 `O(n)`。
- `right` 移动 `n` 次，`left` 最多移动 `n` 次。
- 除返回对象外辅助空间 `O(1)`。

### 测试

```ts
import assert from "node:assert/strict";
import test from "node:test";
import { findPeakRequestWindow } from "./findPeakRequestWindow.js";

test("finds the peak and excludes the right boundary", () => {
  assert.deepEqual(
    findPeakRequestWindow([100, 120, 180, 181, 190], 70),
    { from: 1, toExclusive: 4, count: 3 },
  );
});

test("handles empty, duplicates and tiny windows", () => {
  assert.equal(findPeakRequestWindow([], 10), null);
  assert.deepEqual(
    findPeakRequestWindow([5, 5, 5, 6], 1),
    { from: 0, toExclusive: 3, count: 3 },
  );
  assert.deepEqual(
    findPeakRequestWindow([1, 2, 3], 10),
    { from: 0, toExclusive: 3, count: 3 },
  );
});

test("keeps earliest window on ties", () => {
  assert.deepEqual(
    findPeakRequestWindow([0, 1, 10, 11], 2),
    { from: 0, toExclusive: 2, count: 2 },
  );
});

test("rejects invalid input", () => {
  assert.throws(() => findPeakRequestWindow([2, 1], 10), /sorted/);
  assert.throws(() => findPeakRequestWindow([1], 0), /positive/);
  assert.throws(() => findPeakRequestWindow([Number.NaN], 10), /safe integer/);
});
```

### 失败边界

- 未排序输入会破坏左边界单调排除逻辑。
- 客户端时间可能回拨，不应直接把不可信的设备时钟当全局顺序。
- 一次性加载海量时间戳可能超过内存，离线函数本身不是流处理方案。
- 函数只统计历史峰值，不执行并发安全的准入控制。

### 生产替代方案

- 单实例在线统计可用双端队列保存当前窗口时间戳，并及时移除过期项。
- 分布式限流通常使用带原子脚本的 Redis、令牌桶服务或网关能力，并明确一致性模型。
- 乱序事件流需要 watermark、allowed lateness 与状态过期策略，可交给流处理系统。
- 长期离线分析可让时序数据库或 SQL 窗口查询承担扫描、分区和持久化。
