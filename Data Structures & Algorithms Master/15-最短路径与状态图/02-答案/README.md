# 第 15 章参考答案

## 题 1：Dijkstra

```ts
interface DirectedEdge { readonly id: string; readonly from: string; readonly to: string; readonly weight: number }
interface PathResult { readonly distance: number; readonly nodePath: readonly string[]; readonly edgePath: readonly string[] }
interface QueueEntry { readonly node: string; readonly distance: number; readonly sequence: number }

export function dijkstra(
  nodeIds: readonly string[], edges: readonly DirectedEdge[], source: string,
): ReadonlyMap<string, PathResult | null> {
  const nodes = new Set<string>();
  for (const id of nodeIds) {
    if (!id || nodes.has(id)) throw new Error(`bad/duplicate node: ${id}`);
    nodes.add(id);
  }
  if (!nodes.has(source)) throw new Error(`unknown source: ${source}`);
  const adjacency = new Map<string, DirectedEdge[]>(nodeIds.map((id) => [id, []]));
  const edgeIds = new Set<string>();
  for (const edge of edges) {
    if (!edge.id || edgeIds.has(edge.id)) throw new Error(`bad/duplicate edge: ${edge.id}`);
    edgeIds.add(edge.id);
    if (!nodes.has(edge.from) || !nodes.has(edge.to)) throw new Error(`unknown endpoint: ${edge.id}`);
    if (!Number.isFinite(edge.weight) || edge.weight < 0) throw new Error(`Dijkstra requires nonnegative finite weight: ${edge.id}`);
    adjacency.get(edge.from)!.push(edge);
  }
  for (const list of adjacency.values()) list.sort((a, b) => a.id.localeCompare(b.id));

  const distance = new Map(nodeIds.map((id) => [id, Number.POSITIVE_INFINITY]));
  const previous = new Map<string, { node: string; edgeId: string }>();
  let sequence = 0;
  const heap = new BinaryHeap<QueueEntry>((a, b) =>
    a.distance - b.distance || a.node.localeCompare(b.node) || a.sequence - b.sequence,
  );
  distance.set(source, 0); heap.push({ node: source, distance: 0, sequence: sequence++ });

  while (heap.size > 0) {
    const current = heap.pop()!;
    if (current.distance !== distance.get(current.node)) continue;
    for (const edge of adjacency.get(current.node)!) {
      const candidate = current.distance + edge.weight;
      if (!Number.isFinite(candidate)) throw new RangeError("distance overflow");
      if (candidate < distance.get(edge.to)!) {
        distance.set(edge.to, candidate);
        previous.set(edge.to, { node: current.node, edgeId: edge.id });
        heap.push({ node: edge.to, distance: candidate, sequence: sequence++ });
      }
    }
  }

  const result = new Map<string, PathResult | null>();
  for (const id of nodeIds) {
    const dist = distance.get(id)!;
    if (!Number.isFinite(dist)) { result.set(id, null); continue; }
    const nodePath = [id], edgePath: string[] = [];
    let cursor = id;
    for (let steps = 0; cursor !== source; steps += 1) {
      if (steps >= nodeIds.length) throw new Error("corrupt predecessor cycle");
      const prev = previous.get(cursor);
      if (!prev) throw new Error("missing predecessor");
      edgePath.push(prev.edgeId); cursor = prev.node; nodePath.push(cursor);
    }
    nodePath.reverse(); edgePath.reverse();
    result.set(id, { distance: dist, nodePath: Object.freeze(nodePath), edgePath: Object.freeze(edgePath) });
  }
  return result;
}
```

每个非 stale pop 是当前最小 tentative 距离；非负边保证任何未探索延伸不会先变小再回头改善它。松弛穷尽所有出边，因此最终 dist 最短。lazy entry 可能把同节点多次入堆，stale 检查避免旧距离扩展。

用 Bellman-Ford oracle 做 V-1 轮全边松弛，生成图全部非负；它与 Dijkstra 实现机制不同，适合差分。路径 validator 用 edgeId 查边，检查 from/to 连续与权重和。

## 题 2：风险扩展状态

```ts
interface MigrationStep {
  readonly id: string; readonly from: string; readonly to: string;
  readonly cost: number; readonly riskUnits: number;
}
type MigrationPlan =
  | { readonly status: "ok"; readonly stepIds: readonly string[]; readonly versions: readonly string[]; readonly cost: number; readonly riskUnits: number }
  | { readonly status: "unreachable"; readonly reason: "no enabled path" | "risk budget too small" };

export function planMigration(
  versions: readonly string[], steps: readonly MigrationStep[], current: string, target: string,
  disabledStepIds: ReadonlySet<string>, maxRiskUnits: number, maxStates = 2_000_000,
): MigrationPlan {
  if (!Number.isSafeInteger(maxRiskUnits) || maxRiskUnits < 0) throw new RangeError("bad risk budget");
  const versionSet = new Set(versions);
  if (versionSet.size !== versions.length || !versionSet.has(current) || !versionSet.has(target)) throw new Error("bad versions/current/target");
  const stateCount = versions.length * (maxRiskUnits + 1);
  if (!Number.isSafeInteger(stateCount) || stateCount > maxStates) throw new RangeError(`state budget exceeded: ${stateCount}`);
  const outgoing = new Map<string, MigrationStep[]>(versions.map((v) => [v, []]));
  const ids = new Set<string>();
  for (const step of steps) {
    if (!step.id || ids.has(step.id)) throw new Error(`bad/duplicate step: ${step.id}`);
    ids.add(step.id);
    if (!versionSet.has(step.from) || !versionSet.has(step.to)) throw new Error(`unknown endpoint: ${step.id}`);
    if (!Number.isFinite(step.cost) || step.cost < 0 || !Number.isSafeInteger(step.riskUnits) || step.riskUnits < 0) throw new Error(`bad step cost/risk: ${step.id}`);
    if (!disabledStepIds.has(step.id)) outgoing.get(step.from)!.push(step);
  }
  for (const list of outgoing.values()) list.sort((a, b) => a.id.localeCompare(b.id));

  // 先判断忽略 risk 时是否可达，用于错误分类。
  const seen = new Set([current]); const queue = [current];
  for (let q = 0; q < queue.length; q += 1) for (const edge of outgoing.get(queue[q]!)!) {
    if (!seen.has(edge.to)) { seen.add(edge.to); queue.push(edge.to); }
  }
  if (!seen.has(target)) return { status: "unreachable", reason: "no enabled path" };

  const dist = new Map<string, Float64Array>();
  const prev = new Map<string, Array<{ version: string; risk: number; stepId: string } | null>>();
  for (const v of versions) {
    const row = new Float64Array(maxRiskUnits + 1); row.fill(Number.POSITIVE_INFINITY); dist.set(v, row);
    prev.set(v, Array(maxRiskUnits + 1).fill(null));
  }
  interface State { readonly version: string; readonly risk: number; readonly cost: number; readonly sequence: number }
  let sequence = 0;
  const heap = new BinaryHeap<State>((a, b) =>
    a.cost - b.cost || a.risk - b.risk || a.version.localeCompare(b.version) || a.sequence - b.sequence,
  );
  dist.get(current)![0] = 0; heap.push({ version: current, risk: 0, cost: 0, sequence: sequence++ });

  while (heap.size > 0) {
    const state = heap.pop()!;
    if (state.cost !== dist.get(state.version)![state.risk]) continue;
    for (const step of outgoing.get(state.version)!) {
      const nextRisk = state.risk + step.riskUnits;
      if (nextRisk > maxRiskUnits) continue;
      const nextCost = state.cost + step.cost;
      if (!Number.isFinite(nextCost)) throw new RangeError("migration cost overflow");
      if (nextCost < dist.get(step.to)![nextRisk]!) {
        dist.get(step.to)![nextRisk] = nextCost;
        prev.get(step.to)![nextRisk] = { version: state.version, risk: state.risk, stepId: step.id };
        heap.push({ version: step.to, risk: nextRisk, cost: nextCost, sequence: sequence++ });
      }
    }
  }

  let bestRisk = -1, bestCost = Number.POSITIVE_INFINITY;
  for (let risk = 0; risk <= maxRiskUnits; risk += 1) {
    const cost = dist.get(target)![risk]!;
    if (cost < bestCost) { bestCost = cost; bestRisk = risk; }
  }
  if (bestRisk === -1) return { status: "unreachable", reason: "risk budget too small" };

  const stepIds: string[] = [], path = [target];
  let version = target, risk = bestRisk;
  for (let count = 0; version !== current || risk !== 0; count += 1) {
    if (count > stateCount) throw new Error("corrupt migration predecessor");
    const p = prev.get(version)![risk];
    if (!p) throw new Error("missing migration predecessor");
    stepIds.push(p.stepId); version = p.version; risk = p.risk; path.push(version);
  }
  stepIds.reverse(); path.reverse();
  return {
    status: "ok", stepIds: Object.freeze(stepIds), versions: Object.freeze(path),
    cost: bestCost, riskUnits: bestRisk,
  };
}
```

### 为什么正确、为什么可能太大

每个 `(version,risk)` 是独立节点；每条合法迁移产生非负 cost 的状态边。Dijkstra 在这个扩展图上最短，因此覆盖所有总风险<=R 的原图路径。最后扫描 target 各风险状态先取最低 cost；风险从小到大扫描且只在严格更低时更新，所以 cost 平局保留较低风险。

状态 O(VR)，潜在转移 O(ER)，时间约 O(ER log(VR))，内存 O(VR)。`maxStates` 在分配前检查，但 prev 的对象引用、Map 和 heap 仍有额外常数，阈值必须压测设定。

执行 migration 远比找路径危险：要检查 schema 兼容、备份/恢复、锁、双写、滚动升级、不可逆步骤、审批和审计。planner 的最短 cost 不能自动批准生产变更。若 risk 是主观概率，把它简单相加也可能不符合真实组合风险，必须由领域模型定义。

复写任务：造两条路径——低 cost 超风险、高 cost 合规——逐状态画出 dist；然后把 maxRisk 增加，确认最优路径可能跳变。再解释为什么这不是算法不稳定，而是可行集合改变。

