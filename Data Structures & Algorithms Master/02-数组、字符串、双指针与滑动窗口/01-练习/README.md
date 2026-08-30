# 第 02 章练习

本章恰好两题。第一题训练快慢指针与原地契约，第二题把滑动窗口用于真实流量分析。

## 练习 1：稳定原地去重

### 场景

一批记录已按业务键排序，相同键相邻。为了把数据传给下一阶段，你需要原地压缩重复项，保留每组的第一条记录，并返回有效前缀长度。

### 要求

实现：

```ts
export declare function uniqueSortedInPlace<T>(
  values: T[],
  isSame: (a: T, b: T) => boolean,
): number;
```

约定：

- 相同项在输入中连续出现。
- 每组保留第一次出现的对象，保持组间原有顺序。
- 返回 `newLength`；有效结果为 `values.slice(0, newLength)`。
- 不要求清理有效前缀之后的槽位，也不得调用 `Set`、`Map`、`filter()` 或创建与输入等长的辅助数组。
- 空数组返回 `0`。

### 必测输入

- 空数组、单元素、全相同、全不同。
- 数字重复组。
- 按 `id` 判断相同但其他字段不同的对象，验证保留的是第一条对象引用。

### 验收标准

- 时间 `O(n)`、辅助空间 `O(1)`，并明确说明算法会修改输入。
- 写出 `[0, write)` 的循环不变量。
- 对每个元素最多做常数次读取/比较，不使用反复删除数组项的方式。
- 测试有效前缀，不要错误地假定尾部旧值已被删除。

## 练习 2：定位请求峰值时间窗

### 场景

监控系统拿到一个按时间升序排列的请求时间戳数组，需要找出任意长度为 `windowMs` 的半开时间窗 `[start, start + windowMs)` 中最多包含多少请求，以评估限流阈值。

### 要求

实现：

```ts
export interface PeakWindow {
  from: number;
  toExclusive: number;
  count: number;
}

export declare function findPeakRequestWindow(
  timestamps: readonly number[],
  windowMs: number,
): PeakWindow | null;
```

返回值中的 `[from, toExclusive)` 是原数组下标区间。约定：

- `timestamps` 必须由有限的安全整数构成并按非降序排列，否则抛出明确错误。
- `windowMs` 必须是正安全整数。
- 两个时间戳能处于同一窗口，当且仅当 `later - earlier < windowMs`。
- 空输入返回 `null`。
- 多个窗口请求数相同时，返回 `from` 最小的窗口。
- 不得为每个起点重新扫描，也不得用 `slice()` 构造每个候选窗口。

### 示例

```text
timestamps = [100, 120, 180, 181, 190]
windowMs   = 70

[120, 190) 包含 120、180、181，共 3 项；190 位于右边界，不包含。
返回 { from: 1, toExclusive: 4, count: 3 }
```

### 开放设计问题

说明如果时间戳来自多个节点、可能乱序或迟到，你会如何定义 watermark、允许延迟和内存上限。区分“离线分析”与“真正在线分布式限流”，不要声称本地数组函数能够直接提供全局限流正确性。

### 验收标准

- 时间 `O(n)`、除输出外辅助空间 `O(1)`。
- 明确写出窗口合法性和 `left` 单调移动的不变量。
- 测试重复时间戳、恰好落在右边界、全在一个窗口、窗口极小和空输入。
- 不用时间戳相加判断边界，避免 `start + windowMs` 的安全整数溢出。
