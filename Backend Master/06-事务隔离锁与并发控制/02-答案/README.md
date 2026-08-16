# 第 06 章答案

## 练习 1：并发安全转账

### Schema

```sql
CREATE TABLE app.wallet (
  tenant_id    uuid   NOT NULL,
  id           uuid   NOT NULL,
  balance_cents bigint NOT NULL,
  CONSTRAINT wallet_pk PRIMARY KEY (tenant_id, id),
  CONSTRAINT wallet_tenant_fk FOREIGN KEY (tenant_id)
    REFERENCES app.tenant (id) ON DELETE RESTRICT,
  CONSTRAINT wallet_nonnegative_ck CHECK (balance_cents >= 0)
);
```

### 可复制实现

```ts
import type { Pool } from "pg";

export class TransferRejected extends Error {
  constructor(readonly code: "INVALID_TRANSFER" | "WALLET_NOT_FOUND" | "INSUFFICIENT_FUNDS") {
    super(code);
  }
}

export async function transfer(input: {
  pool: Pool; tenantId: string; fromId: string; toId: string; amountCents: bigint;
}): Promise<void> {
  const { pool, tenantId, fromId, toId, amountCents } = input;
  if (fromId === toId || amountCents <= 0n) throw new TransferRejected("INVALID_TRANSFER");
  const ordered = [fromId, toId].sort();
  const db = await pool.connect();
  try {
    await db.query("BEGIN");
    await db.query("SET LOCAL lock_timeout = '2s'");
    await db.query("SET LOCAL statement_timeout = '4s'");
    await db.query("SELECT set_config('app.tenant_id', $1, true)", [tenantId]);

    const locked = await db.query<{ id: string; balance_cents: string }>(
      `SELECT id, balance_cents
       FROM app.wallet
       WHERE tenant_id = $1::uuid AND id = ANY($2::uuid[])
       ORDER BY id
       FOR UPDATE`,
      [tenantId, ordered],
    );
    if (locked.rowCount !== 2) throw new TransferRejected("WALLET_NOT_FOUND");
    const from = locked.rows.find((row) => row.id === fromId)!;
    if (BigInt(from.balance_cents) < amountCents) {
      throw new TransferRejected("INSUFFICIENT_FUNDS");
    }

    const updated = await db.query(
      `UPDATE app.wallet
       SET balance_cents = balance_cents + CASE
         WHEN id = $2::uuid THEN -$4::bigint
         WHEN id = $3::uuid THEN  $4::bigint
         ELSE 0
       END
       WHERE tenant_id = $1::uuid AND id = ANY($5::uuid[])`,
      [tenantId, fromId, toId, amountCents.toString(), ordered],
    );
    if (updated.rowCount !== 2) throw new Error("locked wallet disappeared");
    await db.query("COMMIT");
  } catch (error) {
    await db.query("ROLLBACK").catch(() => undefined);
    throw error;
  } finally {
    db.release();
  }
}
```

所有事务无论转账方向，都按排序后的 ID 取得锁，消除了这一访问路径的循环等待。`wallet_nonnegative_ck` 仍保留为最终防线。

### 并发验收

```ts
const before = await sumBalances(pool, tenantId);
const jobs = Array.from({ length: 20 }, (_, index) =>
  transfer({
    pool, tenantId,
    fromId: index % 2 === 0 ? walletA : walletB,
    toId: index % 2 === 0 ? walletB : walletA,
    amountCents: 1n,
  }),
);
await Promise.all(jobs);
const rows = await readWallets(pool, tenantId);
assert(rows.every((row) => BigInt(row.balance_cents) >= 0n));
assert.equal(await sumBalances(pool, tenantId), before);
await pool.query("SELECT 1");
```

若金额不足是预期竞争结果，用 `Promise.allSettled` 并只接受 `INSUFFICIENT_FUNDS`；不能吞掉所有 rejection 后只看总额。

### 常见错误与复写

错误做法包括先在事务外读余额、按 from/to 顺序锁、用 JavaScript number 承载 bigint 金额、或持锁调用支付 API。若数据库返回 `40P01`，可在更外层按总 deadline 重跑完整事务，不能只重跑 UPDATE。

复写：增加 append-only `transfer_ledger`，在同一事务记录 operation ID、双方与金额；证明余额变化与 ledger 不会只出现一边。

## 练习 2：阻止 write skew

### Schema 与业务错误

```sql
CREATE TABLE app.shift_assignment (
  tenant_id uuid    NOT NULL,
  shift_id  uuid    NOT NULL,
  doctor_id uuid    NOT NULL,
  on_call   boolean NOT NULL DEFAULT true,
  CONSTRAINT shift_assignment_pk PRIMARY KEY (tenant_id, shift_id, doctor_id),
  CONSTRAINT shift_assignment_tenant_fk FOREIGN KEY (tenant_id)
    REFERENCES app.tenant (id) ON DELETE RESTRICT
);

CREATE INDEX shift_on_call_idx
ON app.shift_assignment (tenant_id, shift_id, doctor_id)
WHERE on_call;
```

```ts
export class LastDoctor extends Error {
  readonly code = "LAST_DOCTOR";
}
```

### 有界 Serializable runner

```ts
import { setTimeout as delay } from "node:timers/promises";
import type { Pool, PoolClient } from "pg";

const retryable = new Set(["40001", "40P01"]);

export async function runSerializable<T>(options: {
  pool: Pool;
  tenantId: string;
  deadlineAt: number;
  maxAttempts?: number;
  operation(db: PoolClient, attempt: number): Promise<T>;
}): Promise<T> {
  const maxAttempts = options.maxAttempts ?? 4;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    if (Date.now() >= options.deadlineAt) {
      throw Object.assign(new Error("transaction retry deadline exceeded"), {
        code: "RETRY_DEADLINE_EXCEEDED",
      });
    }
    const db = await options.pool.connect();
    let retryCause: unknown;
    try {
      const remainingMs = options.deadlineAt - Date.now();
      if (remainingMs <= 0) {
        throw Object.assign(new Error("transaction retry deadline exceeded"), {
          code: "RETRY_DEADLINE_EXCEEDED",
        });
      }
      await db.query("BEGIN ISOLATION LEVEL SERIALIZABLE");
      await db.query("SELECT set_config('statement_timeout', $1, true)", [`${remainingMs}ms`]);
      await db.query("SELECT set_config('app.tenant_id', $1, true)", [options.tenantId]);
      const value = await options.operation(db, attempt);
      await db.query("COMMIT");
      return value;
    } catch (error) {
      await db.query("ROLLBACK").catch(() => undefined);
      const code = (error as { code?: string }).code;
      if (!code || !retryable.has(code) || attempt === maxAttempts) throw error;
      retryCause = error;
    } finally {
      db.release();
    }
    // Backoff only after releasing the failed transaction's pool connection.
    const cap = Math.min(10 * 2 ** (attempt - 1), 100);
    const waitMs = Math.floor(Math.random() * cap);
    if (Date.now() + waitMs >= options.deadlineAt) throw retryCause;
    await delay(waitMs);
  }
  throw new Error("unreachable");
}
```

生产还要给 pool acquisition 配置不超过总预算的等待上限；上面的二次 deadline 检查负责拒绝已经过期才拿到的连接。可注入 clock/random/sleeper 使 retry 测试确定；这里为突出事务语义保持简短。

### 用例

```ts
export async function goOffCall(input: {
  pool: Pool; tenantId: string; shiftId: string; doctorId: string;
  afterRead?: (attempt: number) => Promise<void>;
}): Promise<void> {
  return runSerializable({
    pool: input.pool,
    tenantId: input.tenantId,
    deadlineAt: Date.now() + 2_000,
    operation: async (db, attempt) => {
      const count = await db.query<{ value: number }>(
        `SELECT count(*)::int AS value
         FROM app.shift_assignment
         WHERE tenant_id = $1::uuid AND shift_id = $2::uuid AND on_call`,
        [input.tenantId, input.shiftId],
      );
      if (count.rows[0]!.value <= 1) throw new LastDoctor();
      await input.afterRead?.(attempt); // 测试 barrier；生产不传
      const result = await db.query(
        `UPDATE app.shift_assignment
         SET on_call = false
         WHERE tenant_id = $1::uuid AND shift_id = $2::uuid
           AND doctor_id = $3::uuid AND on_call`,
        [input.tenantId, input.shiftId, input.doctorId],
      );
      if (result.rowCount !== 1) throw new Error("assignment missing or already off-call");
    },
  });
}
```

### 可重复并发测试

第一次 attempt 的 barrier 让两个事务都完成 count 后才继续。Serializable 下一个提交，另一个在 COMMIT 或 UPDATE 收到 `40001`；重试重新 count，随后抛 `LAST_DOCTOR`。最终查询必须为 1。

先把 runner 的 BEGIN 改成 `REPEATABLE READ`，保留同一 barrier，证明两个调用都成功且 count 为 0；否则测试没有真正覆盖 write skew。

### 失败语义与复写

`40001/40P01` 是内部重试信号；预算耗尽才映射暂时不可用。`LAST_DOCTOR` 是稳定业务冲突，不重试。任何邮件、通知或审计外发都应在成功提交后由 outbox 驱动。

常见错误是只重试 COMMIT、在 attempt 间复用旧业务判断、无限重试、没有 jitter，或让测试 barrier 进入生产依赖。

复写：注入 clock、random 与 sleeper，精确测试四次退避和 deadline；为每个 attempt 记录同一逻辑 operation ID 与不同 transaction attempt。
