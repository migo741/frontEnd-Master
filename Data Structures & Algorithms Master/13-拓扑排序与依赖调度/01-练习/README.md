# 第 13 章练习

## 练习 1：稳定 Kahn + 真实 cycle witness（经典机制）

```ts
interface DependencyNode { readonly id: string; readonly dependencies: readonly string[] }
type TopologyResult =
  | { readonly ok: true; readonly order: readonly string[] }
  | { readonly ok: false; readonly cycle: readonly string[] };

declare function topologicalSort(nodes: readonly DependencyNode[]): TopologyResult;
```

拒绝空/重复 ID、未知依赖、重复依赖；self-dependency 可作为长度 2 witness `[A,A]`。ready 按 id 字典序最小优先，输出确定。有环返回首尾相同的真实依赖路径，每相邻 `cycle[i] -> cycle[i+1]` 表示前者依赖后者。

不得用递归 DFS 处理 witness；测试 100,000 深链/大环。对 success 验证每条依赖位置；对 failure 验证 witness 闭合、节点存在、每条边存在。

## 练习 2：受限并发构建计划模拟器（生产/开放）

```ts
interface BuildTask extends DependencyNode {
  readonly duration: number;
  readonly priority: number;
}

declare function simulateBuild(
  tasks: readonly BuildTask[],
  concurrency: number,
  failIds?: ReadonlySet<string>,
): BuildReport;
```

定义 BuildReport：每个任务为 success/failed/blocked；实际运行项记录 start/end；返回 makespan、理论 criticalPath/criticalDuration。ready 在依赖满足后按 priority 高者优先、再 id；running 按 end、id。相同时间完成者先全部 settle，再启动下一批。failIds 中实际运行项在结束时失败；所有下游在依赖全部 settled 后 blocked，无关分支继续。

这是确定性虚拟时间模拟，不用 setTimeout。拒绝环与坏 duration/concurrency；不能因为 topo 数组顺序而串行全部任务。

发散：资源不止“并发槽”而有 CPU/RAM 标签时怎样建模？priority 调度是否可能饥饿？真实任务重试后 critical path 怎样变化？

