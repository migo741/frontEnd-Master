# 第 13 章答案

## 练习一答案：Job Schema 与 claim

```sql
CREATE TABLE job (
  tenant_id uuid NOT NULL,
  id uuid NOT NULL,
  kind text NOT NULL,
  schema_version integer NOT NULL,
  input_ref text NOT NULL,
  status text NOT NULL CHECK (status IN ('queued','running','retry_wait','succeeded','failed','cancelled')),
  step text NOT NULL DEFAULT 'read',
  checkpoint jsonb NOT NULL DEFAULT '{}',
  attempt integer NOT NULL DEFAULT 0,
  max_attempts integer NOT NULL DEFAULT 5,
  next_run_at timestamptz NOT NULL DEFAULT now(),
  lease_owner text,
  lease_until timestamptz,
  fencing bigint NOT NULL DEFAULT 0,
  cancel_requested_at timestamptz,
  result_ref text,
  error_code text,
  version bigint NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(tenant_id,id)
);
CREATE INDEX job_ready_idx ON job(next_run_at,created_at)
  WHERE status IN ('queued','retry_wait');
CREATE INDEX job_expired_lease_idx ON job(lease_until)
  WHERE status='running';
```

claim 在短事务中完成：

```sql
WITH picked AS (
  SELECT tenant_id,id
    FROM job
   WHERE ((status IN ('queued','retry_wait') AND next_run_at <= now())
       OR (status='running' AND lease_until < now()))
     AND cancel_requested_at IS NULL
   ORDER BY next_run_at,created_at
   FOR UPDATE SKIP LOCKED
   LIMIT $1
)
UPDATE job j
   SET status='running', attempt=attempt+1,
       lease_owner=$2, lease_until=now()+$3::interval,
       fencing=fencing+1, version=version+1, updated_at=now()
  FROM picked p
 WHERE j.tenant_id=p.tenant_id AND j.id=p.id
RETURNING j.*;
```

慢工作在提交后进行。heartbeat 与 finish 都验证 generation：

```sql
UPDATE job
   SET lease_until=now()+$5::interval, updated_at=now()
 WHERE tenant_id=$1 AND id=$2 AND status='running'
   AND lease_owner=$3 AND fencing=$4 AND lease_until>now();

UPDATE job
   SET status=CASE WHEN cancel_requested_at IS NULL THEN 'succeeded' ELSE 'cancelled' END,
       result_ref=CASE WHEN cancel_requested_at IS NULL THEN $5 ELSE NULL END,
       lease_owner=NULL, lease_until=NULL,
       version=version+1, updated_at=now()
 WHERE tenant_id=$1 AND id=$2 AND status='running'
   AND lease_owner=$3 AND fencing=$4 AND lease_until>now()
RETURNING status;
```

返回零行时 worker 已失去所有权，绝不能再写 job 或发布完成事件。返回 `cancelled` 时，同一短事务还要插入一个以 result ref 唯一的清理任务；这样进程在删临时 artifact 前崩溃也能由 reconciler 收敛。

TypeScript worker 骨架：

```ts
type Claimed={tenantId:string;id:string;attempt:number;fencing:bigint;step:'read'|'merge';schemaVersion:number}
interface Jobs {
  claim(limit:number,owner:string,leaseMs:number):Promise<Claimed[]>
  heartbeat(j:Claimed,owner:string,leaseMs:number):Promise<boolean>
  checkpoint(j:Claimed,owner:string,next:{step:string;checkpoint:unknown}):Promise<boolean>
  finalize(j:Claimed,owner:string,resultRef:string):Promise<'succeeded'|'cancelled'|'lost'>
  retry(j:Claimed,owner:string,errorCode:string,nextRun:Date):Promise<boolean>
  fail(j:Claimed,owner:string,errorCode:string):Promise<boolean>
}
interface Steps {
  resume(j:Claimed,input:{signal:AbortSignal;operationId:string}):Promise<{ref:string}>
  compensateUnpublished(result:{ref:string}):Promise<void>
}
type Deps={jobs:Jobs;steps:Steps;now():number;random():number}

export async function runOne(j:Claimed,owner:string,deps:Deps,signal:AbortSignal){
  if (j.schemaVersion!==1) return deps.jobs.fail(j,owner,'UNSUPPORTED_SCHEMA')
  try {
    // operationId 属于逻辑 step，跨 attempt/fencing 保持稳定；fencing 只保护本地 owner 写。
    const result=await deps.steps.resume(j,{signal,operationId:`job:${j.id}:step:${j.step}:schema:${j.schemaVersion}`})
    // finalize 在一个事务里验证 owner/fencing，并原子决定 succeeded 或 cancelled。
    const outcome=await deps.jobs.finalize(j,owner,result.ref)
    if(outcome==='lost')throw new Error('LOST_LEASE')
    if(outcome==='cancelled')await deps.steps.compensateUnpublished(result).catch(()=>{})
  } catch(error) {
    if (String(error).includes('LOST_LEASE')) return
    const kind=classify(error)
    if (!kind.retryable || j.attempt>=5) await deps.jobs.fail(j,owner,kind.code)
    else await deps.jobs.retry(j,owner,kind.code,new Date(deps.now()+fullJitter(j.attempt,deps.random,1_000,60_000)))
  }
}

const fullJitter=(attempt:number,random:()=>number,base:number,cap:number)=>
  random()*Math.min(cap,base*2**attempt)
```

artifact 使用不可变 `reports/<tenant>/<job>/<step>/<inputVersion>/<part>`；`putIfAbsent(checksum)` 让 crash 后重做安全。合并前列出 checkpoint 中明确的 parts/checksum，不按前缀盲收攻击者对象。

取消 queued/retry_wait：条件更新到 cancelled；running 只写 `cancel_requested_at`。`finalize` 在锁内决定成功或取消；reconciler 把“已请求取消且 lease 已过期”的 running job 条件更新为 cancelled，并登记临时 artifact 清理。

### 故障测试

使用 fake clock/barrier：worker A claim 后暂停至 lease 过期；B claim 获得更高 fencing 并 complete；恢复 A，A 的 checkpoint/complete rowCount 必须为 0。对象写后 crash，重试命中相同 checksum，不生成第二份业务 artifact。

## 练习二答案：公平与过载

简单且可解释的方案：每 tenant 保持 queued quota；scheduler 每轮最多从每个活跃 tenant claim `weight` 个，再受全局/type semaphore 限制。PostgreSQL 可先选 tenant 的最老 job，再 lateral claim；规模更大时用队列分区 + 独立 fairness dispatcher。

```sql
WITH tenants AS (
  SELECT tenant_id,min(next_run_at) oldest
    FROM job
   WHERE status IN ('queued','retry_wait') AND next_run_at<=now()
   GROUP BY tenant_id ORDER BY oldest LIMIT 100
)
SELECT j.tenant_id,j.id
  FROM tenants t
  JOIN LATERAL (
    SELECT tenant_id,id FROM job
     WHERE tenant_id=t.tenant_id AND status IN ('queued','retry_wait') AND next_run_at<=now()
     ORDER BY next_run_at,created_at
     FOR UPDATE SKIP LOCKED LIMIT 2
  ) j ON true;
```

真实 SQL 要和 UPDATE claim 合在同一事务/CTE。admission 在提交时检查 tenant queued count/配额，超限返回 429；不能先插 10 万再希望 worker 消化。

429 尊重 provider Retry-After，并对 provider 建共享 cooldown；不要让每个 job 自己同时醒来。DLQ 记录 job id、last error code、attempt、handler version；replay API 要权限、reason、数量上限，把状态改回 queued 但 operation id 不变。

指标至少：accepted/rejected、queue oldest age（全局/tenant）、running、success/failure、retry by code、lease expired、DLQ、provider cooldown、cancel latency。告警针对 oldest age SLO、DLQ 增长、lease storm、provider 429、reconciler backlog。

## 常见错误

- 消息 payload 是唯一状态；
- 持行锁调用外部服务；
- ack 成功就认为副作用 exactly once；
- lease 无 fencing，僵尸 worker 可覆盖；
- 所有错误统一重试；
- priority=high 永远压死普通租户；
- DLQ 一键无上限重放。

## 复写验收

跑两个真实 worker 与 fake artifact store，注入每个状态边界 crash。最终每个 job 只有一个 succeeded result，旧 fencing 写全部被拒；恶意 tenant 满队列时普通 tenant 的 oldest age 仍满足阈值。
