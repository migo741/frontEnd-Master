# 练习：从贪心证明到会议资源分配

## 题 1：最大不重叠区间（经典机制）

实现：

```ts
interface Interval {
  readonly id: string;
  readonly start: number;
  readonly end: number;
}

declare function selectMaxCompatible(input: readonly Interval[]): Interval[];
```

契约：

- 使用 `[start,end)`，拒绝非有限值、`start >= end` 和重复 `id`；
- 不修改输入；
- 返回数量最多的互不重叠集合；
- 多个最大解存在时，结果必须确定：按最早结束、再按最早开始、最后按 `id`；
- 时间目标 `O(n log n)`。

交付物不只有代码：写出循环不变量和交换论证；构造“最早开始失败”与“最短时长失败”的最小反例；对 `n <= 12` 写穷举 oracle，用固定 seed 生成随机区间，比较贪心与最优数量。

## 题 2：生产级会议室分配（生产/开放）

实现：

```ts
interface Meeting extends Interval {
  readonly title: string;
}

interface Assignment {
  readonly meetingId: string;
  readonly roomId: number;
}

interface AllocationResult {
  readonly roomCount: number;
  readonly peakConcurrency: number;
  readonly assignments: readonly Assignment[];
}

declare function allocateMeetingRooms(
  meetings: readonly Meeting[],
): AllocationResult;
```

要求：

- 所有会议都必须被安排；同一房间内不重叠；
- 使用最少房间；空闲房间中优先用最小 `roomId`，ID 从 1 开始；
- 同起点时按 `end`、`id` 排序，输出顺序按原输入顺序；
- 输入不可变；错误必须在任何分配发生前被发现；
- 目标 `O(n log n)` 时间、`O(n)` 空间。

测试证据：房间内无冲突、房间数等于独立扫描线 oracle 的峰值、随机打乱输入后在相同 tie-break 下结果稳定。

发散问题（写设计，不要求全部实现）：

1. 会议频繁取消/插入时，重算和增量维护怎样选择？
2. 房间有容量、设备与楼层偏好后，为什么“最少房间”不再是完整目标？
3. 若会议时间仍是本地时间字符串，DST 重复/跳过时刻应在哪一层处理？
4. 数据扩大到一亿条且不能装进内存，怎样做外部排序与分区？

