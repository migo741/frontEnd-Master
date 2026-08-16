# 第 14 章答案

## 练习一答案：Outbox/Inbox Schema

```sql
CREATE TABLE aggregate_order (
  tenant_id uuid NOT NULL,
  id uuid NOT NULL,
  status text NOT NULL CHECK (status IN ('draft','approved','cancelled')),
  version bigint NOT NULL DEFAULT 0,
  PRIMARY KEY(tenant_id,id)
);
CREATE TABLE outbox_event (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  aggregate_type text NOT NULL,
  aggregate_id uuid NOT NULL,
  aggregate_version bigint NOT NULL,
  event_type text NOT NULL,
  schema_version integer NOT NULL,
  payload jsonb NOT NULL,
  payload_hash bytea NOT NULL,
  occurred_at timestamptz NOT NULL,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','publishing','published')),
  lease_owner text, lease_until timestamptz, fencing bigint NOT NULL DEFAULT 0,
  attempts integer NOT NULL DEFAULT 0,
  published_at timestamptz,
  UNIQUE(tenant_id,aggregate_type,aggregate_id,aggregate_version,event_type)
);
CREATE INDEX outbox_pending_idx ON outbox_event(occurred_at)
  WHERE status IN ('pending','publishing');

CREATE TABLE inbox_event (
  consumer text NOT NULL,
  event_id uuid NOT NULL,
  payload_hash bytea NOT NULL,
  processed_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(consumer,event_id)
);
CREATE TABLE invoice (
  tenant_id uuid NOT NULL,
  id uuid NOT NULL,
  order_id uuid NOT NULL,
  source_event_id uuid NOT NULL,
  amount_cents bigint NOT NULL,
  PRIMARY KEY(tenant_id,id),
  UNIQUE(tenant_id,source_event_id)
);
```

生产事务在一个 callback 中完成：

```ts
import {createHash,randomUUID} from 'node:crypto'
type Json=null|boolean|number|string|Json[]|{[key:string]:Json}
const canonicalJson=(x:Json):string=>{
  if(x===null||typeof x==='boolean'||typeof x==='string')return JSON.stringify(x)!
  if(typeof x==='number'){
    if(!Number.isFinite(x))throw new TypeError('NON_FINITE_JSON_NUMBER')
    return JSON.stringify(x)!
  }
  if(Array.isArray(x))return `[${x.map(canonicalJson).join(',')}]`
  return `{${Object.keys(x).sort().map(k=>`${JSON.stringify(k)!}:${canonicalJson(x[k]!)}`).join(',')}}`
}
const hash=(x:Json)=>createHash('sha256').update(canonicalJson(x)).digest()

export async function approveOrder(tx:Tx,tenantId:string,orderId:string,expectedVersion:bigint,amountCents:bigint){
  const changed=await tx.query<{version:bigint}>(
    `UPDATE aggregate_order SET status='approved',version=version+1
      WHERE tenant_id=$1 AND id=$2 AND status='draft' AND version=$3 RETURNING version`,
    [tenantId,orderId,expectedVersion])
  const next=changed.rows[0]?.version
  if (next===undefined) throw new Error('CONFLICT')
  const id=randomUUID(),payload={orderId,amountCents:amountCents.toString()}
  await tx.query(
    `INSERT INTO outbox_event(id,tenant_id,aggregate_type,aggregate_id,aggregate_version,
      event_type,schema_version,payload,payload_hash,occurred_at)
     VALUES($1,$2,'order',$3,$4,'OrderApproved',1,$5,$6,now())`,
    [id,tenantId,orderId,next,payload,hash(payload)])
  return {orderVersion:next,eventId:id}
}
```

金额在事件中用十进制字符串，避免跨语言浮点表示差异。若事件规范允许更复杂数字，再采用团队统一的 canonical JSON 标准；生产者和消费者必须用同一组字节规则。

Relay 的 claim/mark 也必须带 lease 与 fencing：

```sql
WITH picked AS (
  SELECT id FROM outbox_event
   WHERE status='pending' OR (status='publishing' AND lease_until<now())
   ORDER BY occurred_at
   FOR UPDATE SKIP LOCKED LIMIT $1
)
UPDATE outbox_event e
   SET status='publishing',lease_owner=$2,lease_until=now()+$3::interval,
       fencing=fencing+1,attempts=attempts+1
  FROM picked p WHERE e.id=p.id
RETURNING e.*;

UPDATE outbox_event
   SET status='published',published_at=now(),lease_owner=NULL,lease_until=NULL
 WHERE id=$1 AND status='publishing' AND lease_owner=$2 AND fencing=$3
   AND lease_until>now();
```

claim 后提交，再发布 `{eventId,...}`，最后用 owner/fencing mark；慢 publish 要 heartbeat。broker partition key 为 `${tenantId}:${aggregateId}`。mark 前 crash 会重发同 event id。

消费者事务先检测冲突，再写业务：

```ts
export async function consumeApproved(tx:Tx,event:OrderApproved){
  const inserted=await tx.query(
    `INSERT INTO inbox_event(consumer,event_id,payload_hash)
     VALUES('billing',$1,$2) ON CONFLICT DO NOTHING`,[event.id,event.payloadHash])
  if (inserted.rowCount===0) {
    const old=(await tx.query<{payloadHash:Buffer}>(
      `SELECT payload_hash "payloadHash" FROM inbox_event WHERE consumer='billing' AND event_id=$1`,[event.id])).rows[0]
    if (!old?.payloadHash.equals(event.payloadHash)) throw new Error('EVENT_ID_PAYLOAD_CONFLICT')
    return 'duplicate'
  }
  await tx.query(
    `INSERT INTO invoice(tenant_id,id,order_id,source_event_id,amount_cents)
     VALUES($1,$2,$3,$4,$5)`,[event.tenantId,randomUUID(),event.orderId,event.id,event.amountCents])
  return 'applied'
}
```

`inbox_event` insert 与 invoice insert 必须由调用者放同一事务。乱序投影另存 `aggregate_projection.version`；v3 先到则写 gap 表/延迟重试，不直接覆盖 v1。

## 练习二答案：Saga 状态机

```sql
CREATE TABLE order_saga (
  tenant_id uuid NOT NULL,id uuid NOT NULL,order_id uuid NOT NULL,
  status text NOT NULL CHECK (status IN (
    'reserving','authorizing','creating_ticket','capturing','completed',
    'compensating_ticket','voiding_payment','releasing_inventory','compensated','manual_review')),
  version bigint NOT NULL DEFAULT 0,
  failure_code text,
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(tenant_id,id)
);
CREATE TABLE saga_operation (
  saga_id uuid NOT NULL, step text NOT NULL, direction text NOT NULL,
  operation_id uuid NOT NULL UNIQUE, status text NOT NULL,
  external_id text, result jsonb,
  PRIMARY KEY(saga_id,step,direction)
);
```

为每一步预先生成并持久化 operation id，重试不更换。状态转移表：

| 当前 | 成功 | 确定失败 | 未知 |
|---|---|---|---|
| reserving | authorizing | manual/failed | 查库存 operation |
| authorizing | creating_ticket | releasing_inventory | 查支付授权 |
| creating_ticket | capturing | voiding_payment | 按 operation id 查工单 |
| capturing | completed | compensating_ticket | 查 capture，禁止盲重试 |

迟到结果采用 CAS：

```ts
async function advance(tx:Tx,tenantId:string,sagaId:string,expectedVersion:bigint,from:string,to:string){
  const r=await tx.query(
    `UPDATE order_saga SET status=$5,version=version+1,updated_at=now()
      WHERE tenant_id=$1 AND id=$2 AND version=$3 AND status=$4`,
    [tenantId,sagaId,expectedVersion,from,to])
  return r.rowCount===1
}
```

每次 advance 同事务写下一 command outbox。重复 result 由 inbox 去重；不匹配当前状态/version 的迟到 success 不能推进，但要记录并 reconciliation。例如 saga 已开始 void payment，却收到 authorize success：确认该授权 id，然后继续 void，而不是回到 creating_ticket。

补偿逆序：若 ticket 已创建则关闭/标记取消；若 authorization 已成功则 void；释放库存。capture 已确认后，业务可能转为 refund + 人工审批，而非假装回滚。

### 故障注入矩阵

- 每个 step 在外部调用前、调用后、本地提交前 crash；
- provider 超时但查单返回成功；
- 同 result 20 次并发；
- cancel 与 capture result 并发；
- compensation provider 失败直到进入 manual_review；
- v1 worker 与 v2 state 同时滚动，按 saga schema version 路由。

最终断言是钱、库存、工单的业务不变量和 saga 收敛状态，不是“消息只出现一次”。

## 常见错误

- DB commit 后直接 publish，无 outbox；
- relay 重发时生成新 event id；
- inbox 与业务写分两个事务；
- 用 received_at 做全局顺序；
- 把补偿当技术 rollback，忽略权限和失败；
- 外部超时后立即换 operation id 重试。

## 复写验收

kill relay 于 publish/mark 之间，consumer invoice 仍只有一笔；交换 v2/v3 投递顺序，投影不跳过缺口；对 Saga 每个网络边界注入 unknown，必须先查单再决定推进或补偿。
