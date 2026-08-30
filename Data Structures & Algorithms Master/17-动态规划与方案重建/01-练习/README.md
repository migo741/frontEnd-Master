# 练习：从状态定义到可执行选择

## 题 1：可重建方案的 0/1 背包（经典机制）

```ts
interface Item {
  readonly id: string;
  readonly weight: number;
  readonly value: number;
}

interface KnapsackResult {
  readonly maxValue: number;
  readonly totalWeight: number;
  readonly selectedIds: readonly string[];
}

declare function solveKnapsack(
  items: readonly Item[],
  capacity: number,
): KnapsackResult;
```

要求：权重为正整数，价值为非负安全整数，容量为非负整数；拒绝重复 ID 与坏输入；每项至多一次；输入不可变。多个方案同价值时依次选择总重量更小、再选择输入下标序列字典序更小的方案。先写清晰二维版本并重建，再写只返回值的一维版本，解释为何倒序。

测试：空输入、容量 0、单项过重、价值平局、全部可选；对最多 18 项使用子集枚举 oracle；给出正序更新把 0/1 错写成完全背包的最小反例。

## 题 2：离线同步批次规划器（生产/开放）

```ts
interface SyncTask {
  readonly id: string;
  readonly byteUnits: number;
  readonly cpuUnits: number;
  readonly value: number;
  readonly required: boolean;
  readonly expiresAt: number | null;
}

interface BatchPlan {
  readonly selectedIds: readonly string[];
  readonly skipped: Readonly<Record<string, string>>;
  readonly usedByteUnits: number;
  readonly usedCpuUnits: number;
  readonly totalValue: number;
}

declare function planSyncBatch(
  tasks: readonly SyncTask[],
  byteBudget: number,
  cpuBudget: number,
  now: number,
): BatchPlan;
```

契约：先放入未过期 `required` 任务；若它们超预算则整体失败。过期任务不参与。剩余任务在双预算内最大化总价值；平局选更少字节，再更少 CPU，再保持先遇到的方案。所有单位为经过边界层量化的小整数。实现必须设置最大状态数并在超限时明确拒绝，不能因一个请求分配数 GB 内存。

交付：慢速子集 oracle、精确 DP、固定 seed 差分测试、复杂度/内存公式、至少一种大预算替代方案。

发散：

1. 预算是连续字节而非小整数时怎样量化，误差落在哪一侧？
2. 一个任务的 value 会随等待时间变化，状态是否还充分？
3. 多租户要保证最低份额与公平性时怎样拆成两阶段？
4. 任务之间存在依赖时，为什么普通背包会选出不可执行集合？

