# 参考答案：搜索可以指数级，但行为必须诚实

## 题 1

```ts
interface QueensResult {
  readonly firstSolution: readonly number[] | null;
  readonly solutionCount: bigint;
  readonly visitedNodes: number;
}

export function solveNQueens(n: number): QueensResult {
  if (!Number.isInteger(n) || n < 0 || n > 14) throw new RangeError("n must be 0..14");
  const columns = new Set<number>();
  const diagDown = new Set<number>();
  const diagUp = new Set<number>();
  const placement = new Array<number>(n);
  let firstSolution: number[] | null = null;
  let solutionCount = 0n;
  let visitedNodes = 0;

  const search = (row: number): void => {
    visitedNodes += 1;
    if (row === n) {
      solutionCount += 1n;
      firstSolution ??= [...placement];
      return;
    }
    for (let col = 0; col < n; col += 1) {
      const down = row - col;
      const up = row + col;
      if (columns.has(col) || diagDown.has(down) || diagUp.has(up)) continue;

      placement[row] = col;
      columns.add(col); diagDown.add(down); diagUp.add(up);
      search(row + 1);
      columns.delete(col); diagDown.delete(down); diagUp.delete(up);
    }
  };

  search(0);
  return { firstSolution, solutionCount, visitedNodes };
}
```

进入每个递归帧时，`placement[0..row)` 与三个 Set 一一对应且无冲突。合法候选加入后仍满足；递归返回后对称删除，恢复进入前状态。`row` 每层加 1，且最大为 `n`，所以终止。到 `row===n` 时每行一枚且无列/对角线冲突，因此是解；循环尝试当前行所有合法列，所以不会漏解。

最坏时间仍为指数/阶乘量级；三个 Set 和递归深度为 `O(n)`，保存首解 `O(n)`。若漏掉 `diagUp.delete(up)`，之后的兄弟分支会把已经撤销的皇后当成仍存在，通常导致少计甚至误报无解；这是典型状态污染。

独立 validator 应双重循环比较任意两行：列不同且 `abs(r1-r2) !== abs(c1-c2)`。它不复用三个 Set 的实现，以降低“求解器与验证器共享同一个 bug”的风险。

## 题 2

### 表示与传播

`-1/0/1` 分别表示 unknown/false/true。每个搜索分支克隆赋值数组；传播把强制结果写进去，若冲突返回原因。为了让代码可读，下面每轮扫描全部规则直到不再变化；它不是最高性能实现，但容易验证。大模型可进一步建立邻接索引，只检查受本次赋值影响的规则。

```ts
interface ConfigProblem {
  readonly features: readonly string[]; readonly required: readonly string[];
  readonly forbidden: readonly string[]; readonly implies: readonly (readonly [string, string])[];
  readonly conflicts: readonly (readonly [string, string])[];
  readonly exactlyOne: readonly (readonly string[])[];
}
type ConfigResult =
  | { readonly status: "solved"; readonly selected: readonly string[]; readonly visitedNodes: number }
  | { readonly status: "unsatisfiable"; readonly visitedNodes: number; readonly reason: string }
  | { readonly status: "budgetExceeded" | "aborted"; readonly visitedNodes: number };

type Assignment = -1 | 0 | 1;

export function solveFeatureConfig(
  problem: ConfigProblem,
  options: { readonly maxNodes: number; readonly signal?: AbortSignal },
): ConfigResult {
  if (!Number.isSafeInteger(options.maxNodes) || options.maxNodes < 0) {
    throw new RangeError("maxNodes must be a non-negative safe integer");
  }
  const index = new Map<string, number>();
  problem.features.forEach((id, i) => {
    if (index.has(id)) throw new Error(`duplicate feature: ${id}`);
    index.set(id, i);
  });
  const toIndex = (id: string): number => {
    const value = index.get(id);
    if (value === undefined) throw new Error(`unknown feature: ${id}`);
    return value;
  };
  const required = problem.required.map(toIndex);
  const forbidden = problem.forbidden.map(toIndex);
  const implies = problem.implies.map(([a, b]) => [toIndex(a), toIndex(b)] as const);
  const conflicts = problem.conflicts.map(([a, b]) => [toIndex(a), toIndex(b)] as const);
  const groups = problem.exactlyOne.map((g) => {
    if (g.length === 0) throw new Error("exactlyOne group must not be empty");
    const members = g.map(toIndex);
    if (new Set(members).size !== members.length) {
      throw new Error("exactlyOne group contains duplicate features");
    }
    return members;
  });

  const degree = new Int32Array(problem.features.length);
  for (const [a, b] of [...implies, ...conflicts]) {
    degree[a] = degree[a]! + 1;
    degree[b] = degree[b]! + 1;
  }
  for (const g of groups) for (const x of g) degree[x] = degree[x]! + g.length;

  const assign = (state: Int8Array, i: number, value: 0 | 1): string | null => {
    if (state[i] !== -1 && state[i] !== value) return `feature ${problem.features[i]} forced both ways`;
    state[i] = value;
    return null;
  };

  const propagate = (state: Int8Array): string | null => {
    let changed = true;
    while (changed) {
      changed = false;
      const force = (i: number, value: 0 | 1): string | null => {
        if (state[i] === value) return null;
        if (state[i] !== -1) return `feature ${problem.features[i]} forced both ways`;
        state[i] = value; changed = true; return null;
      };
      for (const [a, b] of implies) {
        if (state[a] === 1) { const e = force(b, 1); if (e) return e; }
        if (state[b] === 0) { const e = force(a, 0); if (e) return e; }
      }
      for (const [a, b] of conflicts) {
        if (state[a] === 1) { const e = force(b, 0); if (e) return e; }
        if (state[b] === 1) { const e = force(a, 0); if (e) return e; }
      }
      for (const group of groups) {
        const yes = group.filter((i) => state[i] === 1);
        const unknown = group.filter((i) => state[i] === -1);
        if (yes.length > 1) return "exactlyOne group has multiple selected features";
        if (yes.length === 0 && unknown.length === 0) return "exactlyOne group has no selectable feature";
        if (yes.length === 1) for (const i of unknown) { const e = force(i, 0); if (e) return e; }
        else if (unknown.length === 1) { const e = force(unknown[0]!, 1); if (e) return e; }
      }
    }
    return null;
  };

  const initial = new Int8Array(problem.features.length); initial.fill(-1);
  for (const i of required) { const e = assign(initial, i, 1); if (e) return { status: "unsatisfiable", visitedNodes: 0, reason: e }; }
  for (const i of forbidden) { const e = assign(initial, i, 0); if (e) return { status: "unsatisfiable", visitedNodes: 0, reason: e }; }

  let visitedNodes = 0;
  let stopped: "budgetExceeded" | "aborted" | null = null;
  let lastConflict = "constraints cannot be satisfied";

  const search = (state: Int8Array): Int8Array | null => {
    if (options.signal?.aborted) { stopped = "aborted"; return null; }
    if (visitedNodes >= options.maxNodes) { stopped = "budgetExceeded"; return null; }
    visitedNodes += 1;
    const conflict = propagate(state);
    if (conflict !== null) { lastConflict = conflict; return null; }

    let variable = -1;
    for (let i = 0; i < state.length; i += 1) {
      if (state[i] === -1 && (variable === -1 || degree[i]! > degree[variable]!)) variable = i;
    }
    if (variable === -1) return state;

    for (const value of [1, 0] as const) {
      const next = state.slice(); next[variable] = value;
      const solved = search(next);
      if (solved !== null || stopped !== null) return solved;
    }
    return null;
  };

  const solved = search(initial);
  if (solved !== null) {
    const selected = problem.features.filter((_, i) => solved[i] === 1);
    return { status: "solved", selected, visitedNodes };
  }
  if (stopped !== null) return { status: stopped, visitedNodes };
  return { status: "unsatisfiable", visitedNodes, reason: lastConflict };
}
```

### 必须补的独立验证器

把 selected 转成 Set，逐项检查 required 全在、forbidden 全不在、每条 implication、每对 conflict、每个 exactlyOne 的选中数恰为 1，并拒绝未知 ID。验证器不做搜索，也不调用 `propagate`。

### 正确性、复杂度与局限

传播规则都由原约束逻辑蕴含，不会删除合法解。未确定变量依次尝试 true/false，若完整搜索结束则覆盖全部赋值，因此未找到时可证明无解。达到预算或取消时搜索空间未穷尽，所以返回不同状态。

最坏仍为 `O(2^m × ruleScan)`；克隆状态增加 `O(m)` 每节点成本，递归深度 `O(m)`。示例的 conflict reason 只是最后看到的局部矛盾，不是最小不可满足核心，不能直接展示为完整用户解释。租户可控输入必须限制 feature、规则、group 大小、节点与墙钟时间，并放到隔离执行环境。

复写任务：先删除所有传播，只保留完整赋值后的 validator，记录访问节点；再逐条加入 implication、conflict、exactlyOne 传播，对同一固定问题比较节点数。这样能看到剪枝减少的是搜索量，不是最坏复杂度声明。
