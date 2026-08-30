# 第 15 章练习

## 练习 1：可重建路径的 Dijkstra（经典机制）

```ts
interface DirectedEdge { readonly id: string; readonly from: string; readonly to: string; readonly weight: number }
interface PathResult { readonly distance: number; readonly nodePath: readonly string[]; readonly edgePath: readonly string[] }

declare function dijkstra(
  nodeIds: readonly string[], edges: readonly DirectedEdge[], source: string,
): ReadonlyMap<string, PathResult | null>;
```

拒绝未知端点、重复 ID、非有限或负权；允许零权、平行边和自环。邻接按 edge id 确定，堆按 distance、node id、push sequence 确定；只在严格更短时更新。source 结果距离0/单节点路径；不可达为 null。

使用第10章堆与 stale entry，不实现 O(V²) 扫描版。用 Bellman-Ford 对固定 seed 小图差分；对每个返回 path 独立累计边权并检查连续性。

## 练习 2：带总风险预算的 Schema Migration Planner（生产/开放）

```ts
interface MigrationStep {
  readonly id: string; readonly from: string; readonly to: string;
  readonly cost: number; readonly riskUnits: number;
}
```

输入 versions、steps、current、target、disabledStepIds、maxRiskUnits。找总 risk<=预算的最低 cost 有向路径；平局先较低风险，再保留稳定先发现路径。返回 step IDs、version path、cost、risk；不可达区分“enabled 图根本不可达”和“存在路径但全部超过风险预算”。

使用 `(version,usedRisk)` 扩展状态 Dijkstra；风险为非负安全整数，cost 非负有限。若 `versions*(R+1)` 超过 maxStates，明确拒绝，不能分配失控。禁用边不参与。

发散：风险为连续概率时怎样建模？多个不可比较目标怎样输出 Pareto frontier？迁移步骤执行失败/不可逆时，路径算法之外还需要哪些事务、备份和人工门禁？

