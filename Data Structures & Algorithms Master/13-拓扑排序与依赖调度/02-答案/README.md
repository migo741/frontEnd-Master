# 第 13 章参考答案

## 题 1：稳定拓扑与环证据

下面复用第 10 章 BinaryHeap，比较器负数先出。

```ts
interface DependencyNode { readonly id: string; readonly dependencies: readonly string[] }
type TopologyResult =
  | { readonly ok: true; readonly order: readonly string[] }
  | { readonly ok: false; readonly cycle: readonly string[] };

function buildDependencyMaps(nodes: readonly DependencyNode[]) {
  const dependencies = new Map<string, string[]>();
  for (const node of nodes) {
    if (typeof node.id !== "string" || node.id.trim() === "" || dependencies.has(node.id)) throw new Error(`bad/duplicate id: ${node.id}`);
    const unique = new Set(node.dependencies);
    if (unique.size !== node.dependencies.length) throw new Error(`duplicate dependency: ${node.id}`);
    dependencies.set(node.id, [...node.dependencies].sort((a, b) => a.localeCompare(b)));
  }
  const dependents = new Map<string, string[]>([...dependencies.keys()].map((id) => [id, []]));
  for (const [id, deps] of dependencies) for (const dep of deps) {
    if (!dependencies.has(dep)) throw new Error(`unknown dependency ${dep} of ${id}`);
    dependents.get(dep)!.push(id);
  }
  for (const list of dependents.values()) list.sort((a, b) => a.localeCompare(b));
  return { dependencies, dependents };
}

function findCycle(dependencies: ReadonlyMap<string, readonly string[]>): readonly string[] {
  const color = new Map<string, 0 | 1 | 2>();
  const parent = new Map<string, string>();
  const starts = [...dependencies.keys()].sort((a, b) => a.localeCompare(b));
  for (const start of starts) {
    if ((color.get(start) ?? 0) !== 0) continue;
    color.set(start, 1);
    const stack: Array<{ id: string; next: number }> = [{ id: start, next: 0 }];
    while (stack.length > 0) {
      const frame = stack[stack.length - 1]!;
      const deps = dependencies.get(frame.id)!;
      if (frame.next >= deps.length) { color.set(frame.id, 2); stack.pop(); continue; }
      const dep = deps[frame.next++]!;
      const state = color.get(dep) ?? 0;
      if (state === 0) {
        parent.set(dep, frame.id); color.set(dep, 1); stack.push({ id: dep, next: 0 });
      } else if (state === 1) {
        const middle: string[] = [];
        let current = frame.id;
        while (current !== dep) { middle.push(current); current = parent.get(current)!; }
        middle.reverse();
        return [dep, ...middle, dep];
      }
    }
  }
  throw new Error("cycle expected but not found");
}

export function topologicalSort(nodes: readonly DependencyNode[]): TopologyResult {
  const { dependencies, dependents } = buildDependencyMaps(nodes);
  const indegree = new Map([...dependencies].map(([id, deps]) => [id, deps.length]));
  const ready = new BinaryHeap<string>((a, b) => a.localeCompare(b));
  for (const [id, degree] of indegree) if (degree === 0) ready.push(id);
  const order: string[] = [];
  while (ready.size > 0) {
    const id = ready.pop()!; order.push(id);
    for (const dependent of dependents.get(id)!) {
      const next = indegree.get(dependent)! - 1;
      indegree.set(dependent, next);
      if (next === 0) ready.push(dependent);
    }
  }
  return order.length === nodes.length
    ? { ok: true, order: Object.freeze(order) }
    : { ok: false, cycle: Object.freeze([...findCycle(dependencies)]) };
}
```

Kahn 使用 dependency count 作为 indegree；输出一个节点等价于满足它对 dependents 的一条前置边。每边恰处理一次。稳定堆使 ready tie-break 确定。构图 O(V+E)，稳定排序/堆约 O(E log E 的局部排序上界 + V log V)，空间 O(V+E)；可按需要用输入规范化后的已有顺序减少排序。

DFS witness 的 gray 节点都在显式 stack 当前路径。遇到 current->grayAncestor 后，parent 链确实由 ancestor 走到 current，最后加 back edge，所以返回每条边真实存在。

## 题 2：确定性虚拟计划

### 类型与算法

```ts
interface BuildTask {
  readonly id: string;
  readonly dependencies: readonly string[];
  readonly duration: number;
  readonly priority: number;
}
type RunState = "success" | "failed" | "blocked";
interface TaskRun { readonly id: string; readonly state: RunState; readonly start?: number; readonly end?: number }
interface BuildReport {
  readonly tasks: readonly TaskRun[]; readonly makespan: number;
  readonly criticalPath: readonly string[]; readonly criticalDuration: number;
}

export function simulateBuild(
  tasks: readonly BuildTask[], concurrency: number, failIds: ReadonlySet<string> = new Set(),
): BuildReport {
  if (!Number.isSafeInteger(concurrency) || concurrency <= 0) throw new RangeError("bad concurrency");
  for (const t of tasks) {
    if (!Number.isSafeInteger(t.duration) || t.duration < 0 || !Number.isFinite(t.priority)) throw new Error(`bad task cost: ${t.id}`);
  }
  const topo = topologicalSort(tasks);
  if (!topo.ok) throw new Error(`dependency cycle: ${topo.cycle.join(" -> ")}`);
  const { dependencies, dependents } = buildDependencyMaps(tasks);
  const byId = new Map(tasks.map((t) => [t.id, t] as const));

  // 理论无限并发关键路径。
  const finish = new Map<string, number>();
  const predecessor = new Map<string, string | null>();
  for (const id of topo.order) {
    let bestDep: string | null = null, best = 0;
    for (const dep of dependencies.get(id)!) {
      const value = finish.get(dep)!;
      if (value > best || (value === best && (bestDep === null || dep.localeCompare(bestDep) < 0))) { best = value; bestDep = dep; }
    }
    finish.set(id, best + byId.get(id)!.duration); predecessor.set(id, bestDep);
  }
  let criticalEnd: string | null = null;
  for (const id of topo.order) if (criticalEnd === null || finish.get(id)! > finish.get(criticalEnd)!
      || (finish.get(id) === finish.get(criticalEnd) && id.localeCompare(criticalEnd) < 0)) criticalEnd = id;
  const criticalPath: string[] = [];
  for (let id = criticalEnd; id !== null; id = predecessor.get(id) ?? null) criticalPath.push(id);
  criticalPath.reverse();

  const remaining = new Map([...dependencies].map(([id, deps]) => [id, deps.length]));
  const badDeps = new Map([...dependencies.keys()].map((id) => [id, 0]));
  const state = new Map<string, "pending" | "running" | RunState>([...dependencies.keys()].map((id) => [id, "pending"]));
  const ready = new BinaryHeap<BuildTask>((a, b) => b.priority - a.priority || a.id.localeCompare(b.id));
  for (const t of tasks) if (remaining.get(t.id) === 0) ready.push(t);
  interface Running { readonly id: string; readonly start: number; readonly end: number }
  const running = new BinaryHeap<Running>((a, b) => a.end - b.end || a.id.localeCompare(b.id));
  const runs = new Map<string, TaskRun>();
  let now = 0;

  const settle = (initial: readonly { id: string; outcome: RunState; start?: number; end?: number }[]): void => {
    const queue = [...initial];
    for (let q = 0; q < queue.length; q += 1) {
      const item = queue[q]!;
      state.set(item.id, item.outcome);
      runs.set(item.id, { id: item.id, state: item.outcome, ...(item.start === undefined ? {} : { start: item.start }), ...(item.end === undefined ? {} : { end: item.end }) });
      for (const child of dependents.get(item.id)!) {
        remaining.set(child, remaining.get(child)! - 1);
        if (item.outcome !== "success") badDeps.set(child, badDeps.get(child)! + 1);
        if (remaining.get(child) === 0) {
          if (badDeps.get(child)! > 0) queue.push({ id: child, outcome: "blocked" });
          else ready.push(byId.get(child)!);
        }
      }
    }
  };

  while (runs.size < tasks.length) {
    while (running.size < concurrency && ready.size > 0) {
      const task = ready.pop()!;
      state.set(task.id, "running");
      running.push({ id: task.id, start: now, end: now + task.duration });
    }
    if (running.size === 0) throw new Error("planner stalled despite acyclic graph");
    now = running.peek()!.end;
    const finished: Running[] = [];
    while (running.peek()?.end === now) finished.push(running.pop()!);
    finished.sort((a, b) => a.id.localeCompare(b.id));
    settle(finished.map((run) => ({
      id: run.id, outcome: failIds.has(run.id) ? "failed" as const : "success" as const,
      start: run.start, end: run.end,
    })));
  }

  return {
    tasks: Object.freeze(tasks.map((t) => runs.get(t.id)!)),
    makespan: Math.max(0, ...[...runs.values()].map((r) => r.end ?? 0)),
    criticalPath: Object.freeze(criticalPath),
    criticalDuration: criticalEnd === null ? 0 : finish.get(criticalEnd)!,
  };
}
```

### 关键说明

相同 end 的 running 全部取出、按 id settle 后才下一轮填 ready，避免一个先完成项立即占用槽位而让另一个同刻完成产生的更高优先级任务错过竞争。blocked 不消耗 duration/槽位，但会递归减少下游 remaining。

算法是 list scheduling 模拟，不保证在任意 duration/priority 下得到最小 makespan；资源受限调度本身可能很难。它保证的是契约指定优先规则下的确定结果。critical path 忽略失败和并发资源，只是理论下界。

真实构建执行还需进程隔离、缓存、日志、取消、超时、重试、产物原子发布与持久恢复。本答案只处理 DAG 状态转换。

复写任务：对菱形图手算 concurrency=1/2 的 ready/running/remaining 表，再给一个中间节点失败，确认无关分支仍 success、下游 blocked。不要先看代码。
