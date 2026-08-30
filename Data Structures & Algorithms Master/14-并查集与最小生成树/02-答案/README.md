# 第 14 章参考答案

## 题 1：UnionFind 与 Kruskal

```ts
export class UnionFind {
  readonly #parent: Int32Array;
  readonly #sizes: Int32Array;
  #components: number;
  constructor(size: number) {
    if (!Number.isSafeInteger(size) || size < 0 || size > 0x7fffffff) throw new RangeError("bad size");
    this.#parent = new Int32Array(size);
    this.#sizes = new Int32Array(size);
    for (let i = 0; i < size; i += 1) { this.#parent[i] = i; this.#sizes[i] = 1; }
    this.#components = size;
  }
  get componentCount(): number { return this.#components; }
  find(x: number): number {
    this.#check(x);
    let root = x;
    while (this.#parent[root] !== root) root = this.#parent[root]!;
    while (this.#parent[x] !== x) {
      const next = this.#parent[x]!; this.#parent[x] = root; x = next;
    }
    return root;
  }
  connected(a: number, b: number): boolean { return this.find(a) === this.find(b); }
  union(a: number, b: number): boolean {
    let ra = this.find(a), rb = this.find(b);
    if (ra === rb) return false;
    if (this.#sizes[ra]! < this.#sizes[rb]!) [ra, rb] = [rb, ra];
    this.#parent[rb] = ra;
    this.#sizes[ra] = this.#sizes[ra]! + this.#sizes[rb]!;
    this.#components -= 1;
    return true;
  }
  componentSize(x: number): number { return this.#sizes[this.find(x)]!; }
  #check(x: number): void {
    if (!Number.isSafeInteger(x) || x < 0 || x >= this.#parent.length) throw new RangeError(`bad element: ${x}`);
  }
}

interface WeightedEdge { readonly id: string; readonly u: string; readonly v: string; readonly weight: number }
interface ForestResult {
  readonly selectedEdges: readonly WeightedEdge[]; readonly totalWeight: number;
  readonly componentCount: number;
}

export function minimumSpanningForest(
  nodeIds: readonly string[], edges: readonly WeightedEdge[],
): ForestResult {
  const index = new Map<string, number>();
  nodeIds.forEach((id, i) => {
    if (id.trim() === "" || index.has(id)) throw new Error(`bad/duplicate node: ${id}`);
    index.set(id, i);
  });
  const edgeIds = new Set<string>();
  for (const edge of edges) {
    if (edgeIds.has(edge.id)) throw new Error(`duplicate edge: ${edge.id}`);
    edgeIds.add(edge.id);
    if (!index.has(edge.u) || !index.has(edge.v)) throw new Error(`unknown endpoint: ${edge.id}`);
    if (!Number.isFinite(edge.weight)) throw new Error(`bad weight: ${edge.id}`);
  }
  const ordered = [...edges].sort((a, b) =>
    a.weight - b.weight || a.id.localeCompare(b.id)
      || a.u.localeCompare(b.u) || a.v.localeCompare(b.v),
  );
  const uf = new UnionFind(nodeIds.length);
  const selected: WeightedEdge[] = [];
  let totalWeight = 0;
  for (const edge of ordered) {
    if (uf.union(index.get(edge.u)!, index.get(edge.v)!)) {
      selected.push(edge); totalWeight += edge.weight;
      if (!Number.isFinite(totalWeight)) throw new RangeError("total weight overflow");
    }
  }
  return { selectedEdges: Object.freeze(selected), totalWeight, componentCount: uf.componentCount };
}
```

union 只连接不同 root，所以选边永不成环；原图每条能连接两个当前分量的边最终会被考虑，结束时每个原连通分量被连成一棵树。cut property 保证按权从小到大加入的安全边存在于某个最优森林，归纳得到最小总权。

排序 O(E log E)，DSU 部分摊还 O(E α(V))，空间 O(V+E)。若 weight 是大整数/金额，`a.weight-b.weight` 与浮点累加需要改为安全整数比较或 BigInt 实现。

## 题 2：身份归并计划

```ts
interface CustomerRecord { readonly id: string; readonly tenantId: string; readonly verifiedEmail: string | null }
interface IdentityEvidence {
  readonly id: string; readonly leftId: string; readonly rightId: string;
  readonly kind: "verifiedPhone" | "verifiedExternalId" | "manual";
}
interface MergeGroup {
  readonly canonicalId: string; readonly memberIds: readonly string[];
  readonly evidenceIds: readonly string[];
}
interface ReviewCase extends MergeGroup { readonly reasons: readonly string[] }
interface IdentityPlan {
  readonly autoMerge: readonly MergeGroup[]; readonly review: readonly ReviewCase[];
  readonly unchanged: readonly string[];
}

export function planIdentityMerge(
  records: readonly CustomerRecord[], evidence: readonly IdentityEvidence[],
): IdentityPlan {
  const byId = new Map<string, { record: CustomerRecord; index: number }>();
  records.forEach((record, index) => {
    if (!record.id || !record.tenantId || byId.has(record.id)) throw new Error(`bad/duplicate record: ${record.id}`);
    if (record.verifiedEmail !== null && record.verifiedEmail !== record.verifiedEmail.trim().toLowerCase()) {
      throw new Error(`email must already be canonicalized: ${record.id}`);
    }
    byId.set(record.id, { record: Object.freeze({ ...record }), index });
  });
  const uf = new UnionFind(records.length);
  const evidenceIds = new Set<string>();
  for (const edge of evidence) {
    if (!edge.id || evidenceIds.has(edge.id)) throw new Error(`bad/duplicate evidence: ${edge.id}`);
    evidenceIds.add(edge.id);
    const left = byId.get(edge.leftId), right = byId.get(edge.rightId);
    if (!left || !right) throw new Error(`unknown evidence endpoint: ${edge.id}`);
    if (edge.leftId === edge.rightId) throw new Error(`self evidence: ${edge.id}`);
    uf.union(left.index, right.index);
  }

  const members = new Map<number, string[]>();
  records.forEach((record, i) => {
    const root = uf.find(i); const list = members.get(root) ?? [];
    list.push(record.id); members.set(root, list);
  });
  const edgesByRoot = new Map<number, string[]>();
  for (const edge of evidence) {
    const root = uf.find(byId.get(edge.leftId)!.index);
    const list = edgesByRoot.get(root) ?? []; list.push(edge.id); edgesByRoot.set(root, list);
  }

  const autoMerge: MergeGroup[] = [], review: ReviewCase[] = [], unchanged: string[] = [];
  for (const [root, idsRaw] of members) {
    const ids = idsRaw.sort((a, b) => a.localeCompare(b));
    if (ids.length === 1) { unchanged.push(ids[0]!); continue; }
    const tenants = new Set(ids.map((id) => byId.get(id)!.record.tenantId));
    const emails = new Set(ids.map((id) => byId.get(id)!.record.verifiedEmail).filter((x): x is string => x !== null));
    const reasons: string[] = [];
    if (tenants.size > 1) reasons.push(`cross-tenant component: ${[...tenants].sort().join(", ")}`);
    if (emails.size > 1) reasons.push(`conflicting verified emails: ${[...emails].sort().join(", ")}`);
    const base: MergeGroup = {
      canonicalId: ids[0]!, memberIds: Object.freeze([...ids]),
      evidenceIds: Object.freeze([...(edgesByRoot.get(root) ?? [])].sort((a, b) => a.localeCompare(b))),
    };
    if (reasons.length > 0) review.push({ ...base, reasons: Object.freeze(reasons) });
    else autoMerge.push(base);
  }
  const byCanonical = (a: MergeGroup, b: MergeGroup) => a.canonicalId.localeCompare(b.canonicalId);
  autoMerge.sort(byCanonical); review.sort(byCanonical); unchanged.sort((a, b) => a.localeCompare(b));
  return {
    autoMerge: Object.freeze(autoMerge), review: Object.freeze(review),
    unchanged: Object.freeze(unchanged),
  };
}
```

### 证据、正确性与边界

DSU 对所有 evidence 取无向传递闭包；每记录恰进入一个 component。canonical 使用成员排序而非 root，输出不受 union 顺序影响。冲突只改变计划分类，不丢成员或证据。

这段代码有意不执行合并。真实执行至少要：锁定/版本校验所有记录、写 merge audit、迁移引用、建立 canonical redirect、保证幂等、处理部分失败并提供可逆期。撤回一条 evidence 后，component 可能分裂；普通 DSU 无法“un-union”，应从剩余证据重算受影响组件或采用支持动态连通的更复杂方案。

安全上，“同手机号/外部 ID”仍可能是家庭共享、回收号码或上游错误；kind 只是标签，不是事实保证。阈值、人工审核与租户边界属于领域策略。

复写任务：制造 A-B、B-C，且 A/C 邮箱不同，确认整个三人 component 进入一条 review case并保留两条证据。再删除 B-C 重算，观察普通 DSU 实例为何不能在原地得到两个组件。

