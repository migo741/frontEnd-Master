# 第 12 章参考答案

## 练习 1：BFS、迭代 DFS 与连通分量

### 1. 输入验证与慢 oracle

先验证闭合性，避免遍历中把“未知节点”误当空邻接：

```ts
export type Graph = ReadonlyMap<string, readonly string[]>;

function assertClosed(graph: Graph): void {
  for (const [from, neighbors] of graph) {
    for (const to of neighbors) {
      if (!graph.has(to)) throw new Error(`unknown graph node on edge ${from} -> ${to}`);
    }
  }
}

function reachableSlow(graph: Graph, start: string): Set<string> {
  const reached = new Set<string>([start]);
  let changed = true;
  while (changed) {
    changed = false;
    for (const [from, neighbors] of graph) {
      if (!reached.has(from)) continue;
      for (const to of neighbors) {
        if (!reached.has(to)) {
          reached.add(to);
          changed = true;
        }
      }
    }
  }
  return reached;
}
```

固定点 oracle 可能扫描边很多轮，链图会达到 `O(VE)`，但逻辑直接，适合验证小随机图。

### 2. BFS

```ts
export interface BfsResult {
  readonly order: readonly string[];
  readonly distance: ReadonlyMap<string, number>;
  readonly parent: ReadonlyMap<string, string | null>;
}

function neighbors(graph: Graph, node: string): readonly string[] {
  const value = graph.get(node);
  if (value === undefined) throw new Error(`unknown graph node: ${node}`);
  return value;
}

export function bfs(graph: Graph, start: string): BfsResult {
  assertClosed(graph);
  if (!graph.has(start)) throw new Error(`unknown start node: ${start}`);

  const queue: string[] = [start];
  let head = 0;
  const order: string[] = [];
  const distance = new Map<string, number>([[start, 0]]);
  const parent = new Map<string, string | null>([[start, null]]);

  while (head < queue.length) {
    const current = queue[head];
    head += 1;
    if (current === undefined) throw new Error("unreachable queue index");
    order.push(current);

    const baseDistance = distance.get(current);
    if (baseDistance === undefined) throw new Error("distance invariant broken");

    for (const next of neighbors(graph, current)) {
      if (distance.has(next)) continue; // 入队前即标记
      distance.set(next, baseDistance + 1);
      parent.set(next, current);
      queue.push(next);
    }
  }

  return { order, distance, parent };
}
```

### 3. 带 postorder 的迭代 DFS

```ts
export interface DfsResult {
  readonly preorder: readonly string[];
  readonly postorder: readonly string[];
  readonly parent: ReadonlyMap<string, string | null>;
}

interface DfsFrame {
  readonly node: string;
  readonly neighbors: readonly string[];
  nextIndex: number;
}

export function dfsIterative(graph: Graph, start: string): DfsResult {
  assertClosed(graph);
  if (!graph.has(start)) throw new Error(`unknown start node: ${start}`);

  const preorder: string[] = [start];
  const postorder: string[] = [];
  const parent = new Map<string, string | null>([[start, null]]);
  const visited = new Set<string>([start]);
  const stack: DfsFrame[] = [{ node: start, neighbors: neighbors(graph, start), nextIndex: 0 }];

  while (stack.length > 0) {
    const frame = stack[stack.length - 1];
    if (frame === undefined) throw new Error("unreachable stack state");

    if (frame.nextIndex >= frame.neighbors.length) {
      postorder.push(frame.node);
      stack.pop();
      continue;
    }

    const next = frame.neighbors[frame.nextIndex];
    frame.nextIndex += 1;
    if (next === undefined || visited.has(next)) continue;

    visited.add(next);
    parent.set(next, frame.node);
    preorder.push(next);
    stack.push({ node: next, neighbors: neighbors(graph, next), nextIndex: 0 });
  }

  return { preorder, postorder, parent };
}
```

一个常见错误是先把所有邻居压栈，再立刻把当前节点放入 postorder；那只是“发现邻居后”的顺序，并不表示邻居子树已完成。frame 的 `nextIndex` 正是模拟递归返回点。

### 4. 连通分量

```ts
function assertUndirected(graph: Graph): void {
  assertClosed(graph);
  for (const [from, adjacent] of graph) {
    for (const to of adjacent) {
      if (!neighbors(graph, to).includes(from)) {
        throw new Error(`asymmetric edge ${from} -> ${to}`);
      }
    }
  }
}

export function connectedComponents(graph: Graph): readonly (readonly string[])[] {
  assertUndirected(graph);
  const seen = new Set<string>();
  const components: string[][] = [];

  for (const start of graph.keys()) {
    if (seen.has(start)) continue;
    const queue = [start];
    let head = 0;
    const component: string[] = [];
    seen.add(start);

    while (head < queue.length) {
      const current = queue[head];
      head += 1;
      if (current === undefined) throw new Error("unreachable queue index");
      component.push(current);
      for (const next of neighbors(graph, current)) {
        if (seen.has(next)) continue;
        seen.add(next);
        queue.push(next);
      }
    }
    components.push(component);
  }
  return components;
}
```

### 5. 正确性与复杂度

BFS 入队时标记，所以每个节点最多入队一次。队列按发现次序 FIFO，距离 `d` 节点全部早于距离 `d+1` 节点展开；首次发现给出最少边数。DFS frame 每次要么让 `nextIndex` 增加，要么弹出一个 frame，因此终止；节点只在首次发现时 push，所以有环也不会无限运行。

不计 `assertUndirected` 中 `includes` 的朴素验证，遍历时间 `O(V+E)`、辅助空间 `O(V)`。当前对称验证最坏可能 `O(Σ deg²)`；生产构建阶段应把邻接转 Set 或对边 canonicalize 后比较，不能把验证成本藏起来。

### 6. 测试要点

```ts
const diamond: Graph = new Map([
  ["A", ["B", "C"]],
  ["B", ["D"]],
  ["C", ["D"]],
  ["D", []],
]);

test("BFS discovers diamond join once", () => {
  const result = bfs(diamond, "A");
  assert.deepEqual(result.order, ["A", "B", "C", "D"]);
  assert.equal(result.distance.get("D"), 2);
  assert.equal(result.parent.get("D"), "B");
});

test("iterative DFS records real exit order", () => {
  const result = dfsIterative(diamond, "A");
  assert.deepEqual(result.preorder, ["A", "B", "D", "C"]);
  assert.deepEqual(result.postorder, ["D", "B", "C", "A"]);
});
```

随机图差分时比较集合，不要强迫慢 oracle 与 BFS 有同一发现顺序；顺序是实现契约，可另用固定图断言。

## 练习 2：PackageImpactAnalyzer

### 1. 慢速 oracle

将 changed 加入集合，然后反复扫描所有 package：若某 package 的任一直接依赖已受影响，它也受影响。直到一轮没有新增项。

```ts
function affectedSlow(
  definitions: readonly PackageDefinition[],
  changed: readonly string[],
): Set<string> {
  const affected = new Set(changed);
  let grew = true;
  while (grew) {
    grew = false;
    for (const definition of definitions) {
      if (affected.has(definition.name)) continue;
      if (definition.dependencies.some((dependency) => affected.has(dependency))) {
        affected.add(definition.name);
        grew = true;
      }
    }
  }
  return affected;
}
```

它清楚表达语义，但链形图会扫描很多轮。优化版预建反向邻接并做一次多源 BFS。

### 2. 参考实现

```ts
export interface PackageDefinition {
  readonly name: string;
  readonly dependencies: readonly string[];
}

export interface ImpactRecord {
  readonly packageName: string;
  readonly distance: number;
  readonly source: string;
  readonly chain: readonly string[];
}

export class PackageImpactAnalyzer {
  readonly #dependents = new Map<string, readonly string[]>();

  constructor(definitions: readonly PackageDefinition[]) {
    const names = new Set<string>();
    for (const definition of definitions) {
      if (definition.name.length === 0) throw new TypeError("package name must not be empty");
      if (names.has(definition.name)) throw new Error(`duplicate package: ${definition.name}`);
      names.add(definition.name);
    }

    const building = new Map<string, Set<string>>();
    for (const name of names) building.set(name, new Set<string>());

    for (const definition of definitions) {
      for (const dependency of new Set(definition.dependencies)) {
        if (!names.has(dependency)) {
          throw new Error(`unknown dependency ${definition.name} -> ${dependency}`);
        }
        const reverse = building.get(dependency);
        if (reverse === undefined) throw new Error("reverse index invariant broken");
        reverse.add(definition.name);
      }
    }

    for (const [name, reverse] of building) {
      this.#dependents.set(name, [...reverse].sort());
    }
  }

  analyze(changedPackages: readonly string[]): readonly ImpactRecord[] {
    const sources = [...new Set(changedPackages)].sort();
    for (const source of sources) {
      if (!this.#dependents.has(source)) throw new Error(`unknown changed package: ${source}`);
    }

    const queue: string[] = [];
    let head = 0;
    const distance = new Map<string, number>();
    const parent = new Map<string, string | null>();
    const sourceOf = new Map<string, string>();

    for (const source of sources) {
      queue.push(source);
      distance.set(source, 0);
      parent.set(source, null);
      sourceOf.set(source, source);
    }

    while (head < queue.length) {
      const current = queue[head];
      head += 1;
      if (current === undefined) throw new Error("unreachable queue index");
      const currentDistance = distance.get(current);
      const currentSource = sourceOf.get(current);
      const adjacent = this.#dependents.get(current);
      if (currentDistance === undefined || currentSource === undefined || adjacent === undefined) {
        throw new Error("impact index invariant broken");
      }

      for (const dependent of adjacent) {
        if (distance.has(dependent)) continue;
        distance.set(dependent, currentDistance + 1);
        parent.set(dependent, current);
        sourceOf.set(dependent, currentSource);
        queue.push(dependent);
      }
    }

    const chainFor = (name: string): string[] => {
      const reversed: string[] = [];
      let current: string | null = name;
      while (current !== null) {
        reversed.push(current);
        const previous = parent.get(current);
        if (previous === undefined) throw new Error("parent invariant broken");
        current = previous;
      }
      return reversed.reverse();
    };

    return [...distance.keys()]
      .sort((a, b) => {
        const da = distance.get(a);
        const db = distance.get(b);
        if (da === undefined || db === undefined) throw new Error("distance invariant broken");
        return da - db || a.localeCompare(b);
      })
      .map((packageName) => {
        const d = distance.get(packageName);
        const source = sourceOf.get(packageName);
        if (d === undefined || source === undefined) throw new Error("impact invariant broken");
        return { packageName, distance: d, source, chain: chainFor(packageName) };
      });
  }
}
```

### 3. 正确性

构造时，对于每条 `A -> dependency B`，反向表加入 `B -> dependent A`，所以沿反向边一步恰好表示“直接影响一个依赖者”。多源 BFS 的距离 0 是所有 changed；归纳可知距离 d 的节点具有 d 条真实反向边的传播链。BFS 首次发现最短，同一个 visited 集合让环和自环都终止。parent 来自真实反向边，因此重建链可作为证据。

### 4. 复杂度与规模

- 构造边去重：常见 Set 实现下期望 `O(V+E)`，排序成本 `Σ d log d`。
- 单次 BFS：`O(V+E)`，输出排序 `O(A log A)`，A 为受影响节点数。
- 索引与遍历空间：`O(V+E)`。

百万边时，字符串与小数组对象可能占数百 MB。生产版可以把 package 名映射为连续整数、用 CSR/typed arrays 存反向边，并只在输入输出边界恢复名称。

### 5. 测试与生产边界

构造菱形 `app -> ui, data`、`ui -> tokens`、`data -> tokens`，tokens 改动后 app 距离应为 2 且链只能选择一条确定最短路径。再加入 `a -> b -> a`、`self -> self` 验证终止。随机图把 BFS affected Set 与 `affectedSlow` 比较。

算法正确只说明“给定边集上的可达性正确”。漏掉动态 import、环境条件、生成步骤或工具隐式输入，仍会漏报影响。真正的 affected build 还要把文件到 package、任务输入输出、lockfile、环境和缓存 key 连接起来，并用周期性全量构建发现图漏边。

复写任务：关闭答案，先画正向/反向图，再实现多源 BFS。故意把 visited 移到出队时，测量菱形/稠密图队列增长，解释为何结果可能仍对但资源已经恶化。
