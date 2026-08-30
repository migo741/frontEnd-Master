# 参考答案：从目标函数推导贪心，而不是背模板

## 题 1

### 建模与不变量

朴素 oracle 枚举所有子集，过滤不兼容集合，再取最大数量，复杂度至少 `O(2^n · n log n)`；它只适合小输入验证。

优化依据是交换论证。排序扫描时保持：已选集合合法；`lastEnd` 是最后结束；在相同已选数量下，不存在通过替换已处理区间而得到更早的最后结束时间。于是当前区间起点不早于 `lastEnd` 时，选择它不会减少未来可行空间。

```ts
interface Interval {
  readonly id: string;
  readonly start: number;
  readonly end: number;
}

function validateIntervals(input: readonly Interval[]): void {
  const ids = new Set<string>();
  for (const item of input) {
    if (!Number.isFinite(item.start) || !Number.isFinite(item.end)) {
      throw new TypeError(`interval ${item.id}: time must be finite`);
    }
    if (item.start >= item.end) {
      throw new RangeError(`interval ${item.id}: expected start < end`);
    }
    if (ids.has(item.id)) throw new Error(`duplicate interval id: ${item.id}`);
    ids.add(item.id);
  }
}

export function selectMaxCompatible(
  input: readonly Interval[],
): Interval[] {
  validateIntervals(input);
  const ordered = [...input].sort(
    (a, b) => a.end - b.end || a.start - b.start || a.id.localeCompare(b.id),
  );

  const selected: Interval[] = [];
  let lastEnd = Number.NEGATIVE_INFINITY;
  for (const interval of ordered) {
    if (interval.start >= lastEnd) {
      selected.push(interval);
      lastEnd = interval.end;
    }
  }
  return selected;
}
```

若时间可能超出安全整数，不要使用 `a.end - b.end`；改成 `<`/`>` 分支，或在边界层使用一致的 BigInt 表示。

### 最短时长反例

候选 `[0,3)、[2,4)、[3,6)`。最短的是 `[2,4)`，选后左右两项都冲突，只得到 1 项；选择 `[0,3)` 与 `[3,6)` 可得 2 项。这里平局规则也说明“最短时长”并无充分保证。

### 正确性与复杂度

初始化时空集合合法。每次只在 `start >= lastEnd` 时加入，所以保持不重叠。交换论证保证把任意最优解当前首项换成最早结束项不会减少后续选择数；递归应用于剩余候选，最终数量最优。排序 `O(n log n)`，扫描 `O(n)`，复制与结果占 `O(n)`。

### 小规模穷举思路

对 `n <= 12` 枚举 `mask`，收集对应区间，按开始时间检查相邻项 `previous.end <= current.start`，记录最大数量。随机测试只比较数量，不应强求穷举 oracle 与贪心返回同一组，因为最优解可能不唯一。

## 题 2

### 为什么分配数一定最少

任何时刻有 `p` 场会议同时进行，就至少需要 `p` 个房间，这是不可突破的下界。算法只有在所有现有房间都仍被占用时才创建新房间；创建时当前并发恰好需要这个新房间。因此最终创建数不会超过峰值并发，也不会低于它，故最少。

下面给出本题需要的最小堆。生产项目可复用第 10 章经过测试的通用实现。

```ts
class MinHeap<T> {
  private readonly data: T[] = [];
  constructor(private readonly compare: (a: T, b: T) => number) {}
  get size(): number { return this.data.length; }
  peek(): T | undefined { return this.data[0]; }

  push(value: T): void {
    this.data.push(value);
    let i = this.data.length - 1;
    while (i > 0) {
      const p = Math.floor((i - 1) / 2);
      const parent = this.data[p];
      if (parent === undefined || this.compare(parent, value) <= 0) break;
      this.data[i] = parent;
      i = p;
    }
    this.data[i] = value;
  }

  pop(): T | undefined {
    const oldLength = this.data.length;
    if (oldLength === 0) return undefined;
    const root = this.data[0] as T;
    if (oldLength === 1) {
      this.data.pop();
      return root;
    }
    const last = this.data.pop() as T;
    let i = 0;
    while (true) {
      const left = i * 2 + 1;
      if (left >= this.data.length) break;
      const right = left + 1;
      let child = left;
      if (right < this.data.length && this.compare(this.data[right]!, this.data[left]!) < 0) {
        child = right;
      }
      if (this.compare(last, this.data[child]!) <= 0) break;
      this.data[i] = this.data[child]!;
      i = child;
    }
    this.data[i] = last;
    return root;
  }
}

interface Meeting {
  readonly id: string;
  readonly start: number;
  readonly end: number;
  readonly title: string;
}
interface Assignment { readonly meetingId: string; readonly roomId: number }
interface AllocationResult {
  readonly roomCount: number;
  readonly peakConcurrency: number;
  readonly assignments: readonly Assignment[];
}

interface ActiveRoom { readonly end: number; readonly roomId: number }

export function allocateMeetingRooms(
  meetings: readonly Meeting[],
): AllocationResult {
  validateIntervals(meetings);
  const originalIndex = new Map(meetings.map((m, i) => [m.id, i] as const));
  const ordered = [...meetings].sort(
    (a, b) => a.start - b.start || a.end - b.end || a.id.localeCompare(b.id),
  );
  const active = new MinHeap<ActiveRoom>(
    (a, b) => a.end - b.end || a.roomId - b.roomId,
  );
  const freeRooms = new MinHeap<number>((a, b) => a - b);
  const byMeeting = new Map<string, number>();
  let nextRoomId = 1;
  let peak = 0;

  for (const meeting of ordered) {
    while (active.peek() !== undefined && active.peek()!.end <= meeting.start) {
      freeRooms.push(active.pop()!.roomId);
    }
    const roomId = freeRooms.pop() ?? nextRoomId++;
    byMeeting.set(meeting.id, roomId);
    active.push({ end: meeting.end, roomId });
    peak = Math.max(peak, active.size);
  }

  const assignments = meetings
    .map((m) => ({ meetingId: m.id, roomId: byMeeting.get(m.id)! }))
    .sort((a, b) => originalIndex.get(a.meetingId)! - originalIndex.get(b.meetingId)!);
  return { roomCount: nextRoomId - 1, peakConcurrency: peak, assignments };
}
```

### 测试重点

- `[1,2)`、`[2,3)` 只需一个房间；把释放条件误写为 `<` 会错误地产生两个。
- 多场完全重叠时房间数等于会议数。
- 多个房间同时释放时复用最小 ID。
- 输入验证先完整执行，因此重复 ID 或坏区间不会返回半成品。
- 对随机小输入，独立构造 start/end 事件（同刻 end 在前）计算峰值，并断言 `roomCount === peak`。

### 生产局限

这是一批已知会议的离线单进程算法。频繁在线插入/取消、跨进程并发预订、数据库事务、房间属性、权限、审计和时区解析都不由它解决。生产系统通常需要持久化约束或锁来阻止并发双订，算法结果不能替代一致性协议。

复写任务：关掉答案，只根据“两个堆分别回答什么问题”重写分配器；然后加入 `preferredRoomId`，说明它是否会破坏最少房间保证，以及你的 tie-break 如何变化。
