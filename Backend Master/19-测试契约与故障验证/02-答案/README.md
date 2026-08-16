# 第 19 章答案

## 练习一答案：真实 PostgreSQL 中的 Repository 与并发契约

使用 Vitest、`pg` 和 Testcontainers：

```ts
import { PostgreSqlContainer, type StartedPostgreSqlContainer } from "@testcontainers/postgresql";
import { Pool } from "pg";
import { beforeAll, afterAll, beforeEach, describe, expect, it } from "vitest";
import { readFile } from "node:fs/promises";

let container: StartedPostgreSqlContainer;
let pool: Pool;

beforeAll(async () => {
  container = await new PostgreSqlContainer("postgres:17-alpine").start();
  pool = new Pool({ connectionString: container.getConnectionUri(), max: 8 });
  const migration = await readFile(
    new URL("../../../migrations/001_init.sql", import.meta.url),
    "utf8",
  );
  await pool.query(migration);
}, 120_000);

beforeEach(async () => {
  await pool.query(`
    truncate table tool_intents, agent_runs, memberships, tenants, users
    restart identity cascade
  `);
});

afterAll(async () => {
  await pool?.end();
  await container?.stop();
});
```

Repository 的 claim 使用条件更新，不先查后改：

```ts
type Queryable = Pick<Pool, "query">;

export async function claimIntent(input: {
  pool: Queryable;
  tenantId: string;
  intentId: string;
  workerId: string;
}) {
  const result = await input.pool.query(
    `update tool_intents
       set status = 'executing', lease_owner = $3,
           lease_until = now() + interval '30 seconds'
     where tenant_id = $1 and id = $2
       and status = 'approved' and expires_at > now()
     returning id, tenant_id, status, lease_owner`,
    [input.tenantId, input.intentId, input.workerId],
  );
  return result.rows[0] ?? null;
}
```

确定性竞争测试先取得两个独立连接，再用测试 barrier 同时放行：

```ts
it("only one worker claims an approved intent", async () => {
  const tenantId = "11111111-1111-4111-8111-111111111111";
  const intentId = "22222222-2222-4222-8222-222222222222";
  await seedApprovedIntent(pool, { tenantId, intentId });

  const [ca, cb] = await Promise.all([pool.connect(), pool.connect()]);
  let arrivals = 0;
  let release!: () => void;
  const ready = new Promise<void>((resolve) => { release = resolve; });
  const barrier = async () => {
    arrivals += 1;
    if (arrivals === 2) release();
    await ready;
  };
  try {
    const [one, two] = await Promise.all([
      barrier().then(() => claimIntent({ pool: ca, tenantId, intentId, workerId: "a" })),
      barrier().then(() => claimIntent({ pool: cb, tenantId, intentId, workerId: "b" })),
    ]);
    expect([one, two].filter(Boolean)).toHaveLength(1);
  } finally {
    ca.release();
    cb.release();
  }
});
```

`claimIntent` 参数只要求 `query()`，因此 `Pool` 与 `PoolClient` 都能传入。关键是不同连接与确定起跑点。数据库重启测试应接受稳定的 `DEPENDENCY_UNAVAILABLE`，不能把 `ECONNRESET` 原样泄露给 API。

时间和 ID 注入：

```ts
export interface RuntimeValues {
  now(): Date;
  nextId(): string;
}

const fixedRuntime: RuntimeValues = {
  now: () => new Date("2026-08-16T00:00:00Z"),
  nextId: () => "33333333-3333-4333-8333-333333333333",
};
```

不要用该 clock 假装控制 PostgreSQL `now()`；数据库时间边界要通过固定数据与真实查询单独测试。

## 练习二答案：重复、乱序、重启同时发生的端到端故障测试

先做一个可编程 fake provider，而不是散落布尔开关：

```ts
type Step =
  | { kind: "chunk"; value: string }
  | { kind: "delay"; ms: number }
  | { kind: "error"; error: Error }
  | { kind: "tool_succeeded_then_disconnect"; externalId: string };

export class ScriptedProvider {
  readonly calls: { key: string; runId: string }[] = [];
  readonly effects = new Map<string, { externalId: string }>();

  constructor(private readonly steps: readonly Step[]) {}

  async *run(input: { runId: string; idempotencyKey: string; signal: AbortSignal }) {
    this.calls.push({ key: input.idempotencyKey, runId: input.runId });
    for (const step of this.steps) {
      if (input.signal.aborted) throw input.signal.reason;
      if (step.kind === "delay") await new Promise((r) => setTimeout(r, step.ms));
      if (step.kind === "error") throw step.error;
      if (step.kind === "chunk") yield { type: "token", text: step.value };
      if (step.kind === "tool_succeeded_then_disconnect") {
        this.effects.set(input.idempotencyKey, { externalId: step.externalId });
        throw new Error("CONNECTION_LOST_AFTER_COMMIT");
      }
    }
  }
}
```

消息消费者以 inbox 去重，并在同一事务更新业务状态：

```ts
export async function consumeResult(pool: Pool, message: {
  messageId: string;
  tenantId: string;
  runId: string;
  status: "succeeded" | "failed";
}) {
  const client = await pool.connect();
  try {
    await client.query("begin");
    const inserted = await client.query(
      `insert into inbox_messages (id, tenant_id, received_at)
       values ($1, $2, now()) on conflict do nothing returning id`,
      [message.messageId, message.tenantId],
    );
    if (inserted.rowCount === 0) {
      await client.query("rollback");
      return { kind: "duplicate" } as const;
    }
    const updated = await client.query(
      `update agent_runs set status = $3
       where tenant_id = $1 and id = $2 and status = 'running'
       returning id`,
      [message.tenantId, message.runId, message.status],
    );
    if (updated.rowCount !== 1) throw new Error("INVALID_RUN_TRANSITION");
    await client.query("commit");
    return { kind: "applied" } as const;
  } catch (error) {
    await client.query("rollback");
    throw error;
  } finally {
    client.release();
  }
}
```

测试驱动器每一步都持久检查，而不是仅等最终 UI：

```ts
await api.createRun({ idempotencyKey: "same-key" });
await Promise.all([
  broker.deliver(outboxMessage),
  broker.deliver(outboxMessage),
]);
await worker.checkpointThenCrash(runId);
await worker.restartWithGeneration(2);
await broker.deliver(resultMessage);
await broker.deliver(resultMessage);
await redis.flushall();

expect(await db.countRunsByIdempotencyKey("same-key")).toBe(1);
expect(provider.effects.size).toBeLessThanOrEqual(1);
expect(await db.illegalTransitions(runId)).toEqual([]);
expect(await rebuildProjectionFromPostgres(runId)).toEqual(await api.getRun(runId));
```

如果外部服务不支持 idempotency key，测试应暴露“结果未知”并进入 reconciliation，而不是伪造 exactly-once。迟到模型响应携带旧 generation 时必须被数据库条件更新拒绝。

验收报告应包含故障注入点、预期状态、实际数据库行、外部调用记录和 trace，不只写“测试通过”。

常见错误：所有依赖都 Mock、并发测试共享一个连接、用 sleep 猜时序、测试只看 HTTP 200、让失败重跑掩盖 flaky、使用真实模型导致成本和不稳定。

复写任务：关掉答案，重写 Testcontainers 生命周期、原子 claim、inbox consumer 和 scripted provider，并解释每个测试究竟证明哪条不变量。
