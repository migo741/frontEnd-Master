# 第 20 章练习

## 练习 1：LocalDagExecutor（综合实现）

```ts
interface DagTask {
  readonly id: string;
  readonly dependencies: readonly string[];
  readonly priority: number;
  run(context: { readonly signal: AbortSignal }): unknown | Promise<unknown>;
}

type TaskState = "pending" | "ready" | "running" | "succeeded" | "failed" | "blocked" | "cancelled";
```

实现 `new LocalDagExecutor(tasks,options)`，公开 `done: Promise<ExecutionReport>` 与 `cancel(reason?)`。options 至少含 concurrency、maxTasks、maxEdges、now、onEvent、onObserverError。

要求：构造阶段完整验证 DAG 后才调度；ready 按 priority 高、id 小；不超过并发；task 同步 throw/Promise reject 均 failed；失败迭代阻断所有下游、无关分支继续；取消 pending/ready 并 abort running，等待 running settle；结果按输入顺序；observer throw 隔离。不得递归遍历外部深图，不使用 Promise.all 一次启动所有任务。

用 deferred/barrier 测试，不 sleep。提交状态转移表、复杂度、容量上限、至少一组随机 DAG 性质测试和“task 不遵守 AbortSignal”边界说明。

## 练习 2：审计并替换一个“能跑”的错误执行器（生产审查）

```ts
async function runBuild(tasks: any[]) {
  const byId = Object.fromEntries(tasks.map((t) => [t.id, t]));
  const visited = new Set();
  const order: any[] = [];
  function visit(id: string) {
    if (visited.has(id)) return;
    visited.add(id);
    for (const dep of byId[id].dependencies) visit(dep);
    order.push(id);
  }
  for (const task of tasks) visit(task.id);

  const results = new Map();
  await Promise.all(order.map(async (id) => {
    const value = await byId[id].run();
    results.set(JSON.stringify({ id, deps: byId[id].dependencies }), value);
  }));
  return results;
}
```

至少找出 12 个互不重复的正确性、资源、安全、可维护性问题；每个问题给最小反例/故障，不只贴标签。写 ADR 比较“局部修补”和“状态机重构”，用练习1替换并提供兼容适配层。

benchmark：链、宽 DAG、菱形共享依赖、含环、10% 失败、取消六类 workload；记录最大并发、run 次数、吞吐、p95、内存和结果正确性。给出上线 canary/回滚阈值，而不是只说新版本更快。

发散：若任务有不可重复副作用，重试/崩溃恢复怎样依赖幂等与持久状态？若用户提交 run 代码，隔离边界应放在哪里？

