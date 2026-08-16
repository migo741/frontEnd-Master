# 第 11 章答案

## 练习一答案：上传状态机

```sql
CREATE TABLE stored_object (
  tenant_id uuid NOT NULL,
  id uuid NOT NULL,
  display_name text NOT NULL,
  quarantine_key text NOT NULL UNIQUE,
  final_key text UNIQUE,
  expected_bytes bigint NOT NULL CHECK (expected_bytes BETWEEN 1 AND 52428800),
  expected_sha256 bytea NOT NULL CHECK (octet_length(expected_sha256)=32),
  object_version text,
  detected_type text,
  status text NOT NULL CHECK (status IN ('pending','uploaded','scanning','ready','rejected','deleting','deleted')),
  expires_at timestamptz NOT NULL,
  version bigint NOT NULL DEFAULT 0,
  PRIMARY KEY (tenant_id,id)
);
```

框架无关接口：

```ts
type Head = {bytes: bigint; sha256: string; version: string; contentType: string}
type UploadRow = {
  id:string; tenantId:string; displayName:string; quarantineKey:string; finalKey:string|null
  expectedBytes:bigint; expectedSha256:string; objectVersion:string|null; detectedType:string|null
  status:'pending'|'uploaded'|'scanning'|'ready'|'rejected'|'deleting'|'deleted'
  expiresAt:Date; version:bigint
}
interface Objects {
  signedPut(key:string, constraints:{maxBytes:bigint; expiresSeconds:number}): Promise<string>
  head(key:string): Promise<Head|null>
  copyIfVersion(source:string, sourceVersion:string, target:string): Promise<{version:string}>
  delete(key:string, version?:string): Promise<void>
  signedGet(key:string, version:string, expiresSeconds:number): Promise<string>
}
interface Scanner {scan(key:string, version:string, signal:AbortSignal): Promise<{clean:boolean; detectedType:string}>}
interface ObjectRepo {
  create(row: UploadRow): Promise<void>
  get(tenantId:string,id:string): Promise<UploadRow|null>
  transition(tenantId:string,id:string,expectedVersion:bigint,next:Partial<UploadRow>): Promise<boolean>
}
```

申请时 key 由服务端生成：

```ts
import {randomUUID} from 'node:crypto'

export async function requestUpload(repo:ObjectRepo, objects:Objects, input:{
  tenantId:string; displayName:string; bytes:bigint; sha256:string; now:Date
}) {
  if (input.bytes < 1n || input.bytes > 50n*1024n*1024n) throw new Error('SIZE_LIMIT')
  if (!/^[a-f0-9]{64}$/i.test(input.sha256)) throw new Error('BAD_SHA256')
  const id=randomUUID(), key=`quarantine/${input.tenantId}/${id}`
  await repo.create({id, tenantId:input.tenantId, displayName:safeName(input.displayName),
    quarantineKey:key, finalKey:null, expectedBytes:input.bytes, expectedSha256:input.sha256.toLowerCase(),
    objectVersion:null, detectedType:null, status:'pending', expiresAt:new Date(input.now.getTime()+15*60_000), version:0n})
  return {id, putUrl:await objects.signedPut(key,{maxBytes:input.bytes,expiresSeconds:900})}
}

const safeName=(s:string)=>s.normalize('NFKC').replace(/[\u0000-\u001f\\/]/g,'_').slice(0,120)||'attachment'
```

完成与扫描使用 compare-and-set；省略 HTTP adapter：

```ts
export async function confirmAndScan(repo:ObjectRepo, objects:Objects, scanner:Scanner,
  tenantId:string,id:string,signal:AbortSignal) {
  const row=await repo.get(tenantId,id)
  if (!row) throw new Error('NOT_FOUND')
  if (row.status==='ready') return row
  if (row.status!=='pending' && row.status!=='uploaded') throw new Error('BAD_STATE')
  const head=await objects.head(row.quarantineKey)
  if (!head || head.bytes!==row.expectedBytes || head.sha256.toLowerCase()!==row.expectedSha256) {
    await repo.transition(tenantId,id,row.version,{status:'rejected'}); throw new Error('INTEGRITY_FAILED')
  }
  let currentVersion=row.version
  if (row.status==='pending') {
    if (!await repo.transition(tenantId,id,currentVersion,
      {status:'uploaded',objectVersion:head.version})) throw new Error('CONFLICT')
    currentVersion++
  } else if (row.objectVersion!==head.version) throw new Error('OBJECT_VERSION_CHANGED')
  const scan=await scanner.scan(row.quarantineKey,head.version,signal)
  if (!scan.clean || !['image/png','image/jpeg','application/pdf'].includes(scan.detectedType)) {
    await repo.transition(tenantId,id,currentVersion,{status:'rejected',detectedType:scan.detectedType}); return
  }
  const finalKey=`objects/${tenantId}/${id}/${row.expectedSha256}`
  const copied=await objects.copyIfVersion(row.quarantineKey,head.version,finalKey)
  if (!await repo.transition(tenantId,id,currentVersion,{status:'ready',finalKey,
      objectVersion:copied.version,detectedType:scan.detectedType})) throw new Error('CONFLICT')
}
```

这里不能拿着数据库行锁等待对象存储或病毒扫描；所有远程 I/O 都在短事务外，以 version CAS 收口。生产实现最好显式落 `scanning` lease，避免两个 scanner 重复耗费；重复扫描仍必须无害。下载从 DB 重新授权，只允许 ready，并把 final version 固定到签名 URL。

Reconciler 扫描过期 pending、没有 DB 引用的 quarantine key、deleting 卡住记录；先撤销 DB 可见性，再删除对象。任何异常留状态，下次继续。

## 练习二答案：Webhook inbox 与验签

```sql
CREATE TABLE webhook_inbox (
  provider text NOT NULL,
  event_id text NOT NULL,
  received_at timestamptz NOT NULL DEFAULT now(),
  payload jsonb NOT NULL,
  resource_id text NOT NULL,
  resource_version bigint NOT NULL,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','processing','done','failed')),
  PRIMARY KEY(provider,event_id)
);
CREATE TABLE provider_resource (
  provider text NOT NULL,
  resource_id text NOT NULL,
  version bigint NOT NULL,
  state jsonb NOT NULL,
  PRIMARY KEY(provider,resource_id)
);
```

```ts
import {createHmac,timingSafeEqual} from 'node:crypto'

const mac=(secret:Buffer,timestamp:string,raw:Buffer)=>
  createHmac('sha256',secret).update(timestamp).update('.').update(raw).digest()

export function verifyWebhook(input:{raw:Buffer; timestamp:string; signatureHex:string;
  nowMs:number; secrets:readonly Buffer[]}) {
  const seconds=Number(input.timestamp)
  if (!Number.isSafeInteger(seconds) || Math.abs(input.nowMs-seconds*1000)>300_000) return false
  if (!/^[a-f0-9]{64}$/i.test(input.signatureHex)) return false
  const given=Buffer.from(input.signatureHex,'hex')
  return input.secrets.some(secret=>{
    const expected=mac(secret,input.timestamp,input.raw)
    return given.length===expected.length && timingSafeEqual(given,expected)
  })
}
```

handler 顺序：限制 body（例如 256 KiB）→ verify raw bytes → strict parse → `INSERT ... ON CONFLICT DO NOTHING` → 202/204。重复 event 也返回 2xx，避免提供方持续重试。

worker 更新资源时拒绝倒退：

```sql
INSERT INTO provider_resource(provider,resource_id,version,state)
VALUES ($1,$2,$3,$4)
ON CONFLICT(provider,resource_id) DO UPDATE
SET version=EXCLUDED.version,state=EXCLUDED.state
WHERE provider_resource.version < EXCLUDED.version;
```

若 sequence 不连续或 provider 不保证版本，事件只触发 `fetchCurrent(resourceId)`；adapter 只能访问预配置 base URL，不能接受 payload URL。

SSRF adapter 的关键不变量：HTTPS only；host allowlist；受控 DNS resolver 返回的每个地址都拒绝 private/link-local/loopback；自定义 agent 连接已验证地址并保持 Host/SNI；redirect 每跳重新验证且最多 3 跳；响应头/正文 deadline 和最大字节；不转发用户 Cookie/Authorization。

### 故障测试

- 对同一 event 启动 20 个并发 handler，inbox 只有 1 行；
- 把 JSON key 顺序改变但复用旧签名，应失败，因为签名覆盖 raw bytes；
- 先 v8 后 v7，最终仍为 v8；
- current/previous secret 都可在轮换窗验证，过窗只接受 current；
- redirect 指向 `169.254.169.254`、`::1`、RFC1918、超大 chunked body 均拒绝；
- 处理成功但响应丢失，provider 重发后无重复副作用。

## 常见错误

- 信任扩展名或客户端 Content-Type；
- 扫描后仍允许覆盖同一个对象版本；
- 先解析 JSON 再验签；
- 只用 timestamp、不存 event id；
- 签名正确就无条件执行高风险写；
- URL 初检通过后允许任意 redirect/DNS 重解析。

## 复写验收

从空文件重写 CAS 上传状态机和 raw-body HMAC；用 fake object store 在扫描后替换版本，测试必须阻止 promote。Webhook 并发重放与乱序测试均以数据库最终状态为断言。
