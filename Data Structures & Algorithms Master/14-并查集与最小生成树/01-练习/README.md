# 第 14 章练习

## 练习 1：UnionFind + Kruskal 最小生成森林（经典机制）

```ts
declare class UnionFind {
  constructor(size: number);
  get componentCount(): number;
  find(x: number): number;
  connected(a: number, b: number): boolean;
  union(a: number, b: number): boolean;
  componentSize(x: number): number;
}

interface WeightedEdge { readonly id: string; readonly u: string; readonly v: string; readonly weight: number }
```

UnionFind 使用迭代路径压缩与 union-by-size。Kruskal 输入节点 ID 和无向边；拒绝未知端点、重复 edge ID、非有限 weight；自环合法但永不入选。边按 weight、id、端点稳定排序。断开图返回 forest、componentCount、selectedEdges、totalWeight。

交付：随机 DSU 与慢 label oracle 差分；小图 MST 与穷举 oracle；验证森林边数 `V-components`、无环、每个原连通分量被连接。

## 练习 2：可审计客户身份归并计划（生产/开放）

```ts
interface CustomerRecord {
  readonly id: string;
  readonly tenantId: string;
  readonly verifiedEmail: string | null;
}
interface IdentityEvidence {
  readonly id: string;
  readonly leftId: string;
  readonly rightId: string;
  readonly kind: "verifiedPhone" | "verifiedExternalId" | "manual";
}
```

根据 evidence 无向连通分组。每组 canonicalId 为成员 id 字典序最小；保留组内全部 evidence。若组含多个 tenantId，或多个不同非空 verifiedEmail，输出 review case 和明确 reasons，不进入 autoMerge；其他多成员组输出 merge proposal；单成员可单独列 unchanged。

函数只生成不可变计划，不修改输入/数据库。拒绝未知端点、重复 ID、self evidence 和坏邮箱规范化；结果组、成员、证据顺序确定。

发散：新增证据后如何增量？撤回错误证据为什么普通 DSU 无能为力？真正执行 merge 需要哪些事务、审计、重定向与回滚设计？
