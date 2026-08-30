# 第 20 章参考答案

## 题 1：LocalDagExecutor 核心

下面复用第 10 章 `BinaryHeap` 与第 13 章 `topologicalSort/buildDependencyMaps` 的思想。参考实现刻意保持单一失败策略，便于验证。

```ts
interface DagTask {
  readonly id: string; readonly dependencies: readonly string[]; readonly priority: number;
  run(context: { readonly signal: AbortSignal }): unknown | Promise<unknown>;
}
type TaskState = "pending" | "ready" | "running" | "succeeded" | "failed" | "blocked" | "cancelled";
interface ExecutorEvent {
  readonly sequence: number; readonly taskId: string;
  readonly from: TaskState; readonly to: TaskState; readonly timestamp: number;
}
interface TaskOutcome {
  readonly id: string; readonly state: Exclude<TaskState, "pending" | "ready" | "running">;
  readonly value?: unknown; readonly error?: unknown;
}
interface ExecutionReport { readonly outcomes: readonly TaskOutcome[]; readonly cancelled: boolean }
interface ExecutorOptions {
  readonly concurrency: number; readonly maxTasks: number; readonly maxEdges: number;
  readonly now: () => number;
  readonly onEvent?: (event: ExecutorEvent) => void;
  readonly onObserverError?: (error: unknown) => void;
}
const TERMINAL = new Set<TaskState>(["succeeded", "failed", "blocked", "cancelled"]);

export class LocalDagExecutor {
  readonly done: Promise<ExecutionReport>;
  readonly #tasks = new Map<string, DagTask>();
  readonly #inputOrder: string[];
  readonly #dependents = new Map<string, string[]>();
  readonly #remaining = new Map<string, number>();
  readonly #state = new Map<string, TaskState>();
  readonly #ready = new BinaryHeap<DagTask>((a, b) =>
    b.priority - a.priority || a.id.localeCompare(b.id),
  );
  readonly #controllers = new Map<string, AbortController>();
  readonly #values = new Map<string, unknown>();
  readonly #errors = new Map<string, unknown>();
  #resolveDone!: (report: ExecutionReport) => void;
  #running = 0;
  #terminalCount = 0;
  #eventSequence = 0;
  #pumping = false;
  #cancelled = false;
  #cancelReason: unknown;
  #resolved = false;

  constructor(tasks: readonly DagTask[], private readonly options: ExecutorOptions) {
    if (!Number.isSafeInteger(options.concurrency) || options.concurrency <= 0) throw new RangeError("bad concurrency");
    if (tasks.length > options.maxTasks) throw new RangeError("task limit exceeded");
    let edgeCount = 0;
    for (const input of tasks) {
      edgeCount += input.dependencies.length;
      if (edgeCount > options.maxEdges) throw new RangeError("edge limit exceeded");
      if (!Number.isFinite(input.priority) || typeof input.run !== "function") throw new Error(`bad task: ${input.id}`);
      // 冻结元数据副本，调用方之后不能改依赖。
      const task: DagTask = Object.freeze({
        id: input.id, dependencies: Object.freeze([...input.dependencies]),
        priority: input.priority, run: input.run,
      });
      if (this.#tasks.has(task.id)) throw new Error(`duplicate task: ${task.id}`);
      this.#tasks.set(task.id, task);
    }
    this.#inputOrder = tasks.map((t) => t.id);

    // topologicalSort 负责空ID、重复依赖、未知依赖和环；必须在任何 run 前完成。
    const topo = topologicalSort([...this.#tasks.values()]);
    if (!topo.ok) throw new Error(`dependency cycle: ${topo.cycle.join(" -> ")}`);
    for (const id of this.#tasks.keys()) this.#dependents.set(id, []);
    for (const task of this.#tasks.values()) for (const dep of task.dependencies) this.#dependents.get(dep)!.push(task.id);
    for (const list of this.#dependents.values()) list.sort((a, b) => a.localeCompare(b));

    this.done = new Promise<ExecutionReport>((resolve) => { this.#resolveDone = resolve; });
    for (const task of this.#tasks.values()) {
      this.#remaining.set(task.id, task.dependencies.length);
      this.#state.set(task.id, "pending");
    }
    for (const task of this.#tasks.values()) if (task.dependencies.length === 0) {
      this.#transition(task.id, "ready"); this.#ready.push(task);
    }
    queueMicrotask(() => this.#pump());
  }

  cancel(reason?: unknown): void {
    if (this.#cancelled || this.#resolved) return;
    this.#cancelled = true; this.#cancelReason = reason;
    for (const [id, state] of this.#state) {
      if (state === "pending" || state === "ready") {
        this.#errors.set(id, reason); this.#transition(id, "cancelled");
      }
    }
    for (const controller of this.#controllers.values()) controller.abort(reason);
    this.#checkDone();
  }

  #pump(): void {
    if (this.#pumping) return;
    this.#pumping = true;
    try {
      while (!this.#cancelled && this.#running < this.options.concurrency) {
        let task: DagTask | undefined;
        while (this.#ready.size > 0) {
          const candidate = this.#ready.pop()!;
          if (this.#state.get(candidate.id) === "ready") { task = candidate; break; }
        }
        if (!task) break;
        this.#start(task);
      }
    } finally {
      this.#pumping = false;
      this.#checkDone();
    }
  }

  #start(task: DagTask): void {
    this.#transition(task.id, "running");
    this.#running += 1;
    const controller = new AbortController();
    this.#controllers.set(task.id, controller);
    Promise.resolve()
      .then(() => task.run({ signal: controller.signal }))
      .then(
        (value) => this.#finish(task.id, true, value),
        (error) => this.#finish(task.id, false, error),
      );
  }

  #finish(id: string, succeeded: boolean, payload: unknown): void {
    if (this.#state.get(id) !== "running") return;
    this.#controllers.delete(id); this.#running -= 1;
    if (this.#cancelled) {
      this.#errors.set(id, this.#cancelReason ?? payload);
      this.#transition(id, "cancelled");
    } else if (succeeded) {
      this.#values.set(id, payload); this.#transition(id, "succeeded");
      for (const child of this.#dependents.get(id)!) {
        const next = this.#remaining.get(child)! - 1;
        this.#remaining.set(child, next);
        if (next === 0) {
          if (this.#state.get(child) !== "pending") throw new Error("invalid dependency state");
          this.#transition(child, "ready"); this.#ready.push(this.#tasks.get(child)!);
        }
      }
    } else {
      this.#errors.set(id, payload); this.#transition(id, "failed");
      this.#blockDescendants(id);
    }
    this.#pump();
  }

  #blockDescendants(failedId: string): void {
    const queue = [...this.#dependents.get(failedId)!];
    for (let i = 0; i < queue.length; i += 1) {
      const id = queue[i]!;
      const state = this.#state.get(id)!;
      if (state === "pending" || state === "ready") {
        this.#errors.set(id, new Error(`blocked by failed ancestor ${failedId}`));
        this.#transition(id, "blocked");
        queue.push(...this.#dependents.get(id)!);
      }
    }
  }

  #transition(id: string, to: TaskState): void {
    const from = this.#state.get(id)!;
    if (from === to || TERMINAL.has(from)) throw new Error(`illegal transition ${id}: ${from}->${to}`);
    this.#state.set(id, to);
    if (TERMINAL.has(to)) this.#terminalCount += 1;
    const timestamp = this.options.now();
    const event: ExecutorEvent = {
      sequence: ++this.#eventSequence, taskId: id, from, to, timestamp,
    };
    try { this.options.onEvent?.(event); }
    catch (error) { try { this.options.onObserverError?.(error); } catch { /* double observer failure isolated */ } }
  }

  #checkDone(): void {
    if (this.#resolved || this.#terminalCount !== this.#tasks.size || this.#running !== 0) return;
    this.#resolved = true;
    const outcomes: TaskOutcome[] = this.#inputOrder.map((id) => {
      const state = this.#state.get(id)! as TaskOutcome["state"];
      return {
        id, state,
        ...(this.#values.has(id) ? { value: this.#values.get(id) } : {}),
        ...(this.#errors.has(id) ? { error: this.#errors.get(id) } : {}),
      };
    });
    this.#resolveDone({ outcomes: Object.freeze(outcomes), cancelled: this.#cancelled });
  }
}
```

### 关键审查

`topologicalSort` 的输入类型只需 id/dependencies，因此 DagTask 可兼容。它必须使用前文已经修正的稳定、迭代 cycle witness 版本。

`#blockDescendants` 可能把同一汇合节点多次放入 queue，但第一次后 state=blocked，之后不继续传播，结果正确；超大菱形图可增加 visited Set，减少重复扫描。`onEvent` 的 now 若返回 NaN 不影响调度正确性但污染观测；生产构造应验证/包装时钟。

取消后 running 任务 resolve 仍记 cancelled，这是明确契约；它们的返回值不发布。若任务忽略 signal 永不 settle，done 永不 resolve。若需要强制终止，把 run 放到可杀的 Worker/进程，并定义副作用隔离。

复杂度：验证/建图 O(V+E) 加 topo heap；运行 O(V log V+E)，空间 O(V+E)。ready stale entry 最多每个任务一个，因为每任务只 ready 一次。

### 测试骨架

用 deferred 让 A/B 同时 ready、concurrency=2；C 依赖 A/B。断言启动记录先有 A/B、没有 C；resolve A 后仍无 C；resolve B 后 C 才启动。让 A reject，C/D 后代 blocked，独立 E success。cancel 时检查 running task 收到 `signal.aborted===true`，手工 resolve 后 done 才完成。

observer 在第3个事件抛错，执行结果仍正确且 onObserverError 被调用。随机 DAG 为每 task 计数 runCalls，最终所有 succeeded task 的 deps 都 succeeded、每项<=1。

## 题 2：错误执行器审计

至少包括以下问题及反例：

1. `any[]` 让输入契约消失；`dependencies:null` 到运行才崩。
2. Object.fromEntries 对重复 ID 静默后者覆盖；两个任务只运行一个。
3. 普通对象键 `__proto__` 等有原型/字典语义风险。
4. 未知 dependency 访问 `byId[id]` 为 undefined。
5. visited 只有二色，A->B->A 被当“访问过”而不是报告环，仍产生 order。
6. 递归 visit 遇 100k 深链栈溢出。
7. 依赖重复未拒绝，模型含义不明。
8. Promise.all 会立即启动 order 中全部任务；数组顺序不建立 await 依赖，dependent 可先产生副作用。
9. 无并发上限，十万任务同时开 socket/文件。
10. 一个 reject 使 Promise.all 立刻 reject，但其他任务仍在后台运行，调用方误以为停止。
11. 没有 failed/blocked 区分，下游照样运行。
12. 没有取消/AbortSignal，页面离开或部署停止无法协作终止。
13. run 同步抛错/observer/错误上下文没有结构化状态。
14. `JSON.stringify` 复合键受依赖顺序影响，且根本不是结果检索需要；结果 Map 无容量/生命周期。
15. 输出按完成时序写 Map，稳定性依赖运行竞争。
16. 调用方可在 visit 后修改 tasks/dependencies，验证与执行不是同一快照。
17. 没有限制任务/边/ID/payload，易被资源耗尽。
18. 用户 run 代码与主进程同权限，无 sandbox/secret 边界。

ADR 应选择状态机重构，因为局部给 Promise.all 加 concurrency 并不能补 cycle、失败传播、取消和可观察状态。兼容层可把旧 `{id,dependencies,run}` 映射 DagTask，done success 结果再转旧 Map；遇失败返回新结构化错误，先灰度记录差异。

benchmark 不只测速度：

- 链：验证不提前启动、深度不爆栈；
- 宽图：最大 running 恰不超 concurrency；
- 菱形：共享 dependent 只运行一次；
- 环：零 run 调用并返回 witness；
- 失败：下游 blocked、无关 success；
- 取消：信号、停止新启动、done 语义。

固定生成 seed、Node 版本、机器与任务模拟方式；分别报告构图时间、执行器自身开销、p50/p95、峰值 RSS/heap、事件数。canary 可设：任何依赖前启动/重复 run/并发超限立即回滚；性能如 p95 增加>20%或内存>预算触发回滚，但阈值应根据真实基线设定。

最终发散：把执行状态持久化前，先写出幂等 task key、claim lease、attempt、heartbeat、result version、retry/backoff 和 crash recovery 状态机。没有这些字段，“把 Map 换成数据库”仍不是可靠分布式执行器。

