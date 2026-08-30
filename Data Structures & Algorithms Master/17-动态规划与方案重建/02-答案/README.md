# 参考答案：让状态含义驱动实现

## 题 1

### 二维表与重建

为保持教学清晰，先用二维表。这里把平局定义为“不选当前项”，可稳定偏向较早输入；最终再比较总重量。如果你要严格实现题目所述完整字典序 tie-break，可为状态保存路径比较信息，但会增加成本。下面通过扫描最小容量实现“同价值先选更轻”，相同容量下表格的“不在平局更新”保持先遇到方案。

```ts
interface Item { readonly id: string; readonly weight: number; readonly value: number }
interface KnapsackResult {
  readonly maxValue: number;
  readonly totalWeight: number;
  readonly selectedIds: readonly string[];
}

function validate(items: readonly Item[], capacity: number): void {
  if (!Number.isSafeInteger(capacity) || capacity < 0) throw new RangeError("bad capacity");
  const ids = new Set<string>();
  for (const x of items) {
    if (ids.has(x.id)) throw new Error(`duplicate id: ${x.id}`);
    ids.add(x.id);
    if (!Number.isSafeInteger(x.weight) || x.weight <= 0) throw new RangeError(`bad weight: ${x.id}`);
    if (!Number.isSafeInteger(x.value) || x.value < 0) throw new RangeError(`bad value: ${x.id}`);
  }
}

export function solveKnapsack(items: readonly Item[], capacity: number): KnapsackResult {
  validate(items, capacity);
  const dp = Array.from({ length: items.length + 1 }, () =>
    new Float64Array(capacity + 1),
  );

  for (let i = 1; i <= items.length; i += 1) {
    const item = items[i - 1]!;
    for (let c = 0; c <= capacity; c += 1) {
      const without = dp[i - 1]![c]!;
      const withItem = c >= item.weight
        ? dp[i - 1]![c - item.weight]! + item.value
        : Number.NEGATIVE_INFINITY;
      dp[i]![c] = withItem > without ? withItem : without;
    }
  }

  const maxValue = dp[items.length]![capacity]!;
  let bestCapacity = 0;
  while (bestCapacity <= capacity && dp[items.length]![bestCapacity] !== maxValue) {
    bestCapacity += 1;
  }

  const selected: string[] = [];
  let c = bestCapacity;
  for (let i = items.length; i > 0; i -= 1) {
    const item = items[i - 1]!;
    if (c >= item.weight && dp[i]![c]! > dp[i - 1]![c]!) {
      selected.push(item.id);
      c -= item.weight;
    }
  }
  selected.reverse();
  return { maxValue, totalWeight: bestCapacity, selectedIds: selected };
}

export function knapsackValueOnly(items: readonly Item[], capacity: number): number {
  validate(items, capacity);
  const dp = new Float64Array(capacity + 1);
  for (const item of items) {
    for (let c = capacity; c >= item.weight; c -= 1) {
      dp[c] = Math.max(dp[c]!, dp[c - item.weight]! + item.value);
    }
  }
  return dp[capacity]!;
}
```

注意 `Float64Array` 的值仍是 JS number；这里验证输入安全整数，但价值总和也应做上界预算。严谨实现可在累加时检查 `Number.isSafeInteger`。

### 正确性

二维表归纳不变量：第 `i` 行每格是前 `i` 项在容量 `c` 下的最优值。任意合法方案要么不含当前项，落入 `dp[i-1][c]`；要么含当前项，去掉它后落入 `dp[i-1][c-w]`。转移取两类最大值，既不会漏，也不会产生非法方案。

时间 `O(nC)`，二维空间 `O(nC)`；一维空间 `O(C)`。重建 `O(n+C)`，其中扫描最小可达容量为 `O(C)`。

## 题 2

### 先处理业务硬约束

必须任务不是“价值特别高”的普通项；把硬约束伪装成大价值可能溢出，也不能保证绝对优先。先验证并扣除 required 任务预算，再优化可选任务。过期任务先排除。

双预算 DP 的状态 `best[b][c]` 表示恰好使用 `b` 字节单位、`c` CPU 单位时的最大价值；不可达为 `-Infinity`。倒序更新保证每任务至多一次。为恢复方案，改善状态时保存不可变链式 trace。

```ts
interface SyncTask {
  readonly id: string; readonly byteUnits: number; readonly cpuUnits: number;
  readonly value: number; readonly required: boolean; readonly expiresAt: number | null;
}
interface BatchPlan {
  readonly selectedIds: readonly string[]; readonly skipped: Readonly<Record<string, string>>;
  readonly usedByteUnits: number; readonly usedCpuUnits: number; readonly totalValue: number;
}
interface Trace { readonly taskIndex: number; readonly previous: Trace | null }

const MAX_STATES = 2_000_000;

export function planSyncBatch(
  tasks: readonly SyncTask[], byteBudget: number, cpuBudget: number, now: number,
): BatchPlan {
  for (const x of [byteBudget, cpuBudget, now]) {
    if (!Number.isSafeInteger(x) || x < 0) throw new RangeError("budgets/now must be safe non-negative integers");
  }
  const ids = new Set<string>();
  for (const t of tasks) {
    if (ids.has(t.id)) throw new Error(`duplicate id: ${t.id}`);
    ids.add(t.id);
    if (![t.byteUnits, t.cpuUnits, t.value].every(Number.isSafeInteger)
        || t.byteUnits < 0 || t.cpuUnits < 0 || t.value < 0) {
      throw new RangeError(`invalid task: ${t.id}`);
    }
  }

  const skipped: Record<string, string> = {};
  const requiredIds: string[] = [];
  let requiredBytes = 0, requiredCpu = 0, requiredValue = 0;
  const optional: Array<{ task: SyncTask; originalIndex: number }> = [];

  tasks.forEach((task, originalIndex) => {
    if (task.expiresAt !== null && task.expiresAt <= now) {
      skipped[task.id] = "expired";
    } else if (task.required) {
      requiredIds.push(task.id);
      requiredBytes += task.byteUnits;
      requiredCpu += task.cpuUnits;
      requiredValue += task.value;
    } else {
      optional.push({ task, originalIndex });
    }
  });
  if (requiredBytes > byteBudget || requiredCpu > cpuBudget) {
    throw new Error("required tasks exceed batch budget");
  }

  const B = byteBudget - requiredBytes;
  const C = cpuBudget - requiredCpu;
  const states = (B + 1) * (C + 1);
  if (!Number.isSafeInteger(states) || states > MAX_STATES) {
    throw new RangeError(`DP state budget exceeded: ${states}`);
  }
  const value = new Float64Array(states);
  value.fill(Number.NEGATIVE_INFINITY);
  const trace: Array<Trace | null> = Array(states).fill(null);
  const index = (b: number, c: number): number => b * (C + 1) + c;
  value[index(0, 0)] = 0;

  optional.forEach(({ task }, taskIndex) => {
    for (let b = B; b >= task.byteUnits; b -= 1) {
      for (let c = C; c >= task.cpuUnits; c -= 1) {
        const from = index(b - task.byteUnits, c - task.cpuUnits);
        if (value[from] === Number.NEGATIVE_INFINITY) continue;
        const to = index(b, c);
        const candidate = value[from]! + task.value;
        if (candidate > value[to]!) {
          value[to] = candidate;
          trace[to] = { taskIndex, previous: trace[from] ?? null };
        }
      }
    }
  });

  let bestB = 0, bestC = 0;
  for (let b = 0; b <= B; b += 1) {
    for (let c = 0; c <= C; c += 1) {
      const current = value[index(b, c)]!;
      const best = value[index(bestB, bestC)]!;
      if (current > best || (current === best && (b < bestB || (b === bestB && c < bestC)))) {
        bestB = b; bestC = c;
      }
    }
  }

  const optionalIds: string[] = [];
  const chosen = new Set<string>();
  for (let p: Trace | null = trace[index(bestB, bestC)] ?? null; p !== null; p = p.previous) {
    const id = optional[p.taskIndex]!.task.id;
    optionalIds.push(id); chosen.add(id);
  }
  optionalIds.reverse();
  for (const { task } of optional) if (!chosen.has(task.id)) skipped[task.id] = "not selected within budgets";

  return {
    selectedIds: [...requiredIds, ...optionalIds], skipped,
    usedByteUnits: requiredBytes + bestB, usedCpuUnits: requiredCpu + bestC,
    totalValue: requiredValue + value[index(bestB, bestC)]!,
  };
}
```

### 证据与局限

处理完前 `i` 个可选任务后，每个可达状态保存该精确资源用量的最大价值。倒序使同一任务不会进入自己的前驱。最终扫描所有预算内状态，先取最大价值，再取较低资源，因此满足契约。

时间 `O(nBC)`，空间 `O(BC)`，trace 数组引用还会带来显著对象分配；`MAX_STATES` 只是示例，应由进程内存预算和压测数据决定。对于巨大连续预算，可采用量化、Pareto frontier、业务分桶或近似策略。若任务有依赖，需把依赖闭包纳入决策；普通背包无法阻止选择子任务却漏掉前置任务。

测试时对 `n <= 20` 枚举子集，先过滤过期、检查 required，再比较所有预算内集合。不要靠 `sleep`；时间由参数 `now` 注入。还应测试状态上限、全部过期、required 恰好用完预算、零资源任务和价值平局。

复写任务：先只实现 value-only 双预算版本；确认随机差分通过后再加 trace。然后把 byte 单位从 1 KiB 改成 64 KiB，说明向上取整如何保证不超真实预算，以及可能损失多少可用容量。
