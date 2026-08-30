# 第 12 章练习

本章恰好两题。第一题实现可证明的基础遍历；第二题处理真实 package 图的方向、规模与解释性。

## 练习 1：稳定 BFS、迭代 DFS 与无向连通分量

给定闭合邻接表：

```ts
export type Graph = ReadonlyMap<string, readonly string[]>;

export interface BfsResult {
  readonly order: readonly string[];
  readonly distance: ReadonlyMap<string, number>;
  readonly parent: ReadonlyMap<string, string | null>;
}

export interface DfsResult {
  readonly preorder: readonly string[];
  readonly postorder: readonly string[];
  readonly parent: ReadonlyMap<string, string | null>;
}

export declare function bfs(graph: Graph, start: string): BfsResult;
export declare function dfsIterative(graph: Graph, start: string): DfsResult;
export declare function connectedComponents(graph: Graph): readonly (readonly string[])[];
```

契约：

- 每个邻居必须也是 graph 的 key，否则在遍历前抛出包含 from/to 的错误。
- 邻接数组顺序就是稳定探索顺序；重复邻居允许存在，但同一节点最多发现一次。
- start 不存在时抛错。
- BFS 的 distance 是最少边数，parent 可重建一条最短路径。
- DFS 必须使用显式栈，不依赖递归调用栈；preorder 在首次进入时记录，postorder 在全部邻居完成后记录。
- `connectedComponents` 的前置条件是无向图：每条 `u -> v` 都必须存在 `v -> u`；否则拒绝。节点按 graph key 插入顺序启动分量遍历，每个分量使用 BFS 顺序。
- 不修改 graph 或邻接数组，不使用 `Array.shift()`。

验证要求：链、菱形、有向环、自环、断开图、未知邻居、非对称“无向”图；对 BFS 检查每条 parent 边真实存在且 `distance[parent] + 1 === distance[node]`。随机小图与慢速固定点可达 oracle 比较。

发散问题：若图有 1000 万整数节点，如何把 `Map<string,string[]>` 改为整数 ID、typed array/CSR 表示？只需画内存布局并分析，不要求实现。

## 练习 2：PackageImpactAnalyzer

输入 package 清单：

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

export declare class PackageImpactAnalyzer {
  constructor(definitions: readonly PackageDefinition[]);
  analyze(changedPackages: readonly string[]): readonly ImpactRecord[];
}
```

方向约定：定义中的 `A.dependencies = [B]` 表示边 `A -> B`，即 A 依赖 B。B 变化会影响 A，因此分析沿反向 dependents 图传播。

要求：

- package name 必须非空且唯一；未知 dependency 在构造时拒绝。
- 重复依赖边去重；自依赖和更大的环允许存在，分析不得无限循环。
- changedPackages 必须全部已知，重复 changed 去重；空 changed 返回空数组。
- 多源 BFS：changed 自身包含在结果中，distance 0、source 为自身、chain 只有自身。
- 其他节点的 distance 是到任一 changed source 的最少反向边数；chain 必须是一条真实最短传播链。
- 结果按 distance 升序、再按 packageName 字典序；同距离多条最短链时，通过“changed 排序、每个 dependents 邻接表排序、首次发现”得到确定 source/chain。
- 构造目标 `O(V + E + 排序成本)`，单次分析 `O(V + E)`（不计最终结果排序）；不得为每个 package 重新 DFS。

生产案例至少包括：菱形依赖、多 changed、循环依赖、重复边、自环、未知 dependency、未知 changed、完全不相关的 package。用“反复扫描所有依赖边直到不再变化”的慢 oracle 验证 affected 集合。

开放问题：真实 monorepo 的条件导出、动态 import、生成代码和测试-only dependency 是否都算影响边？写一页 ADR，区分“图算法正确”和“图数据完整”两类风险。
