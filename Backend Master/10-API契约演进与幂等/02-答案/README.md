# 第 10 章答案

## 练习一答案：数据库协议

```sql
CREATE TABLE idempotency_record (
  tenant_id uuid NOT NULL,
  actor_id uuid NOT NULL,
  operation text NOT NULL,
  key text NOT NULL CHECK (length(key) BETWEEN 16 AND 200),
  request_hash bytea NOT NULL CHECK (octet_length(request_hash)=32),
  status text NOT NULL CHECK (status IN ('processing','completed','failed')),
  response_status integer,
  response_body jsonb,
  owner_token uuid NOT NULL,
  operation_id uuid NOT NULL UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL,
  PRIMARY KEY (tenant_id, actor_id, operation, key),
  CHECK ((status='processing' AND response_status IS NULL AND response_body IS NULL) OR
         (status IN ('completed','failed') AND response_status IS NOT NULL AND response_body IS NOT NULL))
);

CREATE TABLE refund (
  tenant_id uuid NOT NULL,
  id uuid NOT NULL,
  ticket_id uuid NOT NULL,
  operation_id uuid NOT NULL,
  amount_cents bigint NOT NULL CHECK (amount_cents > 0),
  status text NOT NULL CHECK (status IN ('accepted','rejected')),
  PRIMARY KEY (tenant_id,id),
  UNIQUE (tenant_id,operation_id)
);
```

请求 fingerprint 必须对已经解析、规范化的业务输入计算，而非原始 JSON 空格；字段顺序要固定。

```ts
import {createHash, randomUUID} from 'node:crypto'

type RefundInput = Readonly<{ticketId: string; amountCents: bigint; expectedVersion: bigint}>
const canonical = (x: RefundInput) => JSON.stringify({
  ticketId: x.ticketId,
  amountCents: x.amountCents.toString(),
  expectedVersion: x.expectedVersion.toString(),
})
const sha = (s: string) => createHash('sha256').update(s).digest()

type Replay = {kind: 'owner'; operationId: string} | {kind: 'replay'; status: number; body: unknown} | {kind: 'busy'}
interface RefundRepo {
  claim(scope: IdemScope, hash: Buffer, owner: string, proposedOperationId: string): Promise<Replay>
  transactRefundAndFinish(args: RefundInput & {tenantId:string; operationId:string},
    scope:IdemScope,owner:string): Promise<{status:number; body:unknown}>
}

export async function createRefund(repo: RefundRepo, scope: Scope, key: string, input: RefundInput) {
  const owner = randomUUID(), proposedOperationId = randomUUID(), requestHash = sha(canonical(input))
  const idemScope = {...scope, key}
  const claim = await repo.claim(idemScope, requestHash, owner, proposedOperationId)
  if (claim.kind === 'replay') return claim
  if (claim.kind === 'busy') return {kind:'busy' as const, retryAfterSeconds:1}
  const operationId = claim.operationId // 从记录取得；lease owner 更换时也绝不更换
  // adapter 在同一 PostgreSQL 事务内写 refund 与 completed 响应。
  const response = await repo.transactRefundAndFinish(
    {...input, tenantId:scope.tenantId, operationId},idemScope,owner)
  return {kind:'replay' as const, ...response}
}

type Scope = {tenantId:string; actorId:string; operation:string}
type IdemScope = Scope & {key:string}
```

更强的实现把业务写与 `completed` 响应放在同一 PostgreSQL 事务中。`claim` 算法：

1. `INSERT ... ON CONFLICT DO NOTHING`；插入成功者是 owner，并永久保存本次业务 `operation_id`。
2. 冲突后读取 row；hash 不同立即 `409 IDEMPOTENCY_KEY_REUSED`。
3. completed/failed 返回保存的 status/body。
4. processing 且 owner 仍活跃，短轮询或返回 `409 REQUEST_IN_PROGRESS`。
5. owner lease 过期不能直接重做外部副作用；新 owner 继续使用记录中的同一个 operation id，先做 reconciliation。

事务示意：

```sql
BEGIN;
SELECT status, request_hash, owner_token
  FROM idempotency_record
 WHERE tenant_id=$1 AND actor_id=$2 AND operation=$3 AND key=$4
 FOR UPDATE;

UPDATE ticket
   SET version=version+1
 WHERE tenant_id=$1 AND id=$5 AND version=$6 AND status='approved';
-- row_count 必须为 1，否则写稳定 409 响应

INSERT INTO refund(tenant_id,id,ticket_id,operation_id,amount_cents,status)
VALUES ($1,$7,$5,$8,$9,'accepted');

UPDATE idempotency_record
   SET status='completed', response_status=201, response_body=$10
 WHERE tenant_id=$1 AND actor_id=$2 AND operation=$3 AND key=$4 AND owner_token=$11;
COMMIT;
```

如果支付是外部调用，不要在持锁事务中请求网络；事务创建 refund/outbox，返回 `202`，由第 13–14 章的 worker 以 operation id 推进。

### 并发测试

```ts
it('two first requests create one refund', async () => {
  const [a,b] = await Promise.all([
    api.refund({key:'intent-0123456789', body}),
    api.refund({key:'intent-0123456789', body}),
  ])
  expect([a.status,b.status].every(x => [201,409].includes(x))).toBe(true)
  expect(await sql.countRefundsForIntent('intent-0123456789')).toBe(1)
  const replay = await api.refund({key:'intent-0123456789', body})
  expect(replay.body).toEqual(a.status === 201 ? a.body : b.body)
})
```

不要断言并发响应顺序；断言数据库不变量和最终重放。

## 练习二答案：兼容演进

推荐保持 v1：新增可选 `assigneeV2` 不改变旧 `assigneeName`，服务端内部统一模型由两个 adapter 投影；新增状态先让旧消费者支持 unknown，再开始产生该值。若无法更新旧 consumer，则 v1 映射 `waiting_customer -> open`，v2 暴露精确状态。

```ts
type DomainTicket = {id:string; status:'open'|'waiting_customer'|'closed'; assignee:{id:string; displayName:string}|null}
type V1Ticket = {id:string; status:'open'|'closed'; assigneeName:string|null}
type V2Ticket = {id:string; status:'open'|'waiting_customer'|'closed'; assignee:{id:string; displayName:string}|null}

export const toV1 = (t: DomainTicket): V1Ticket => ({
  id:t.id,
  status:t.status === 'waiting_customer' ? 'open' : t.status,
  assigneeName:t.assignee?.displayName ?? null,
})
export const toV2 = (t: DomainTicket): V2Ticket => ({...t})
```

offset 与 cursor 响应可在迁移期并存：v1 继续 page/total，v2 提供稳定 `(createdAt,id)` cursor。不要把 cursor 塞进旧 `page` 字段。

Consumer fixture 使用真实发布包或 HTTP：

```ts
it('new provider still satisfies frozen v1 consumer', async () => {
  const raw: unknown = await provider.get('/v1/tickets/t-1')
  const parsed = frozenV1Schema.parse(raw)
  expect(['open','closed']).toContain(parsed.status)
  expect(typeof parsed.assigneeName === 'string' || parsed.assigneeName === null).toBe(true)
})
```

CI 规则：OpenAPI diff 删除字段/响应、收紧输入、增加必填、改变类型或状态码即阻断；新增 optional 仍运行 consumer fixtures。仪表盘按 API version、client id/version 统计请求，达到书面阈值后才停止 v1。

## 常见错误

- key 只按字符串全局作用域，造成跨租户冲突/探测；
- 同 key 不校验请求 fingerprint；
- 事务提交后超时，客户端换新 key 重试；
- 把所有 500 都缓存或都释放，忽略副作用未知状态；
- response 直接序列化 ORM entity；
- 认为增加 enum 值永远向后兼容。

## 复写验收

从空数据库跑 50 个并发相同 key，请求完成后只有一条业务记录；kill 进程模拟提交后丢响应，重启后同 key 能恢复原结果。冻结 v1 consumer fixture，在实现 v2 后仍应通过。
