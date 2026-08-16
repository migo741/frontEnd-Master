# 第 09 章答案

## 练习一答案：Schema、RLS 与策略

```sql
CREATE TABLE tenant (
  id uuid PRIMARY KEY,
  name text NOT NULL
);
CREATE TABLE membership (
  tenant_id uuid NOT NULL REFERENCES tenant(id),
  user_id uuid NOT NULL,
  role text NOT NULL CHECK (role IN ('agent','manager','support')),
  policy_version bigint NOT NULL DEFAULT 1,
  PRIMARY KEY (tenant_id, user_id)
);
CREATE TABLE ticket (
  tenant_id uuid NOT NULL REFERENCES tenant(id),
  id uuid NOT NULL,
  assignee_id uuid,
  status text NOT NULL CHECK (status IN ('open','approved','refunded','closed')),
  amount_cents bigint NOT NULL CHECK (amount_cents >= 0),
  version bigint NOT NULL DEFAULT 0,
  PRIMARY KEY (tenant_id, id)
);
CREATE TABLE ticket_comment (
  tenant_id uuid NOT NULL,
  id uuid NOT NULL,
  ticket_id uuid NOT NULL,
  body text NOT NULL,
  PRIMARY KEY (tenant_id, id),
  FOREIGN KEY (tenant_id, ticket_id) REFERENCES ticket(tenant_id, id)
);

ALTER TABLE ticket ENABLE ROW LEVEL SECURITY;
ALTER TABLE ticket FORCE ROW LEVEL SECURITY;
CREATE POLICY ticket_tenant ON ticket
  USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);
```

部署 Web 角色不能是表 owner，也不能有 `BYPASSRLS`。每个请求使用一个事务：

```ts
interface Tx {
  query<T>(sql: string, params?: readonly unknown[]): Promise<{rows: T[]; rowCount: number}>
}
interface Db {transaction<T>(run: (tx: Tx) => Promise<T>): Promise<T>}

export async function inTenant<T>(db: Db, tenantId: string, run: (tx: Tx) => Promise<T>) {
  return db.transaction(async tx => {
    await tx.query(`SELECT set_config('app.tenant_id', $1, true)`, [tenantId])
    const check = await tx.query<{tenant: string}>(`SELECT current_setting('app.tenant_id') tenant`)
    if (check.rows[0]?.tenant !== tenantId) throw new Error('TENANT_CONTEXT_FAILED')
    return run(tx)
  })
}
```

第三个参数 `true` 等价 transaction-local；不要把 tenant 插值进 SQL。

```ts
type Principal = {userId: string; tenantId: string; role: 'agent'|'manager'|'support'; policyVersion: bigint}
type Ticket = {tenantId: string; id: string; assigneeId: string|null; status: string; amountCents: bigint; version: bigint}
type Action = 'read'|'update'|'refund'
type Decision = {allow: true} | {allow: false; reason: string}

export function decide(p: Principal, action: Action, t: Ticket): Decision {
  if (p.tenantId !== t.tenantId) return {allow: false, reason: 'TENANT'}
  if (p.role === 'support') return {allow: false, reason: 'SUPPORT_REQUIRES_BREAK_GLASS'}
  if (action === 'read') {
    return p.role === 'manager' || t.assigneeId === p.userId
      ? {allow: true} : {allow: false, reason: 'RELATION'}
  }
  if (action === 'update') return p.role === 'manager'
    ? {allow: true} : {allow: false, reason: 'ROLE'}
  return p.role === 'manager' && t.status === 'approved' && t.amountCents <= 100_000n
    ? {allow: true} : {allow: false, reason: 'REFUND_POLICY'}
}
```

事务内读取并条件更新：

```ts
export async function refund(db: Db, p: Principal, id: string, expectedVersion: bigint) {
  return inTenant(db, p.tenantId, async tx => {
    const found = await tx.query<Ticket>(
      `SELECT tenant_id "tenantId", id, assignee_id "assigneeId", status,
              amount_cents "amountCents", version
         FROM ticket WHERE tenant_id=$1 AND id=$2 FOR UPDATE`, [p.tenantId, id])
    const ticket = found.rows[0]
    if (!ticket) throw new Error('NOT_FOUND')
    const decision = decide(p, 'refund', ticket)
    if (!decision.allow) throw new Error(`FORBIDDEN:${decision.reason}`)
    const changed = await tx.query(
      `UPDATE ticket SET status='refunded', version=version+1
       WHERE tenant_id=$1 AND id=$2 AND version=$3 AND status='approved'`,
      [p.tenantId, id, expectedVersion])
    if (changed.rowCount !== 1) throw new Error('CONFLICT')
    await tx.query(
      `INSERT INTO audit_event(tenant_id, actor_id, action, resource_id, policy_version)
       VALUES ($1,$2,'ticket:refund',$3,$4)`,
      [p.tenantId, p.userId, id, p.policyVersion])
  })
}
```

### 必测不变量

用两个非 owner 数据库连接和真实事务验证：

```ts
for (const route of ['get','list','search','batch','refund'] as const) {
  it(`${route}: tenant A never observes B`, async () => {
    const observed = await invoke(route, principalA, ticketB.id)
    expect(JSON.stringify(observed)).not.toContain(ticketB.secretMarker)
  })
}
```

另测未设置 `app.tenant_id` 返回零行而非全表；普通角色不能 `SET ROLE` 或关闭 RLS；同一连接先跑 A 再跑 B 不残留 A。

## 练习二答案：授权感知导出

建议 schema：

```sql
CREATE TABLE export_job (
  tenant_id uuid NOT NULL,
  id uuid NOT NULL,
  requested_by uuid NOT NULL,
  membership_policy_version bigint NOT NULL,
  filter jsonb NOT NULL,
  status text NOT NULL CHECK (status IN ('queued','running','ready','revoked','failed')),
  object_key text,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, id)
);
```

队列只放 `{tenantId, jobId}`；worker 以受限角色调用 `inTenant`，重新读取 job 和当前 membership。常规导出采用“执行时仍有权限”，被移出则置 `revoked`；若合规业务要求批准快照，必须有审批记录、范围、过期时间和专用执行身份，不能把旧角色字符串当授权。

对象 key 由服务端生成：`tenant/<tenantId>/exports/<random>.csv.enc`。bucket 私有；下载 API 重新鉴权后签发 60 秒 URL。不要把用户提供的文件名当 key，也不要把长期 URL写入通知。

```ts
export async function runExport(db: Db, storage: Storage, tenantId: string, jobId: string) {
  return inTenant(db, tenantId, async tx => {
    const job = (await tx.query<ExportJob>(
      `SELECT * FROM export_job WHERE tenant_id=$1 AND id=$2 FOR UPDATE`, [tenantId, jobId])).rows[0]
    if (!job || job.status !== 'queued') return
    const member = (await tx.query(
      `SELECT 1 FROM membership WHERE tenant_id=$1 AND user_id=$2`, [tenantId, job.requestedBy])).rows[0]
    if (!member) {
      await tx.query(`UPDATE export_job SET status='revoked' WHERE tenant_id=$1 AND id=$2`, [tenantId, jobId])
      return
    }
    // 大数据生产中先 claim/commit，再流式读取；示例强调重新授权与 tenant 上下文。
  })
}
```

缓存 key 使用 `export-download:v1:{tenantId}:{userId}:{jobId}:{policyVersion}`。跨租户 support 必须走 break-glass：工单原因、短期 grant、双人批准和完整审计。

## 常见错误

- `SELECT ... WHERE id=$1` 后才比较 tenant；
- 测试使用数据库 owner，误以为 RLS 生效；
- GraphQL DataLoader 跨请求/租户复用；
- 把管理员当无条件超级用户；
- job 创建时检查一次，此后永远信任 payload；
- 签名 URL 有效数天且可转发。

## 复写验收

在真实 PostgreSQL 测试中故意删除 repository 的 tenant 条件，确认 RLS 仍拒绝；再使用错误的普通 `SET` 写一个连接池串租户回归，修为事务内 `set_config(..., true)`。
