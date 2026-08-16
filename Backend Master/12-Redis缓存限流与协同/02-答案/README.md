# 第 12 章答案

## 练习一答案：版本化 cache-aside

缓存值明确版本：

```ts
type Membership = Readonly<{tenantId:string; userId:string; role:'agent'|'manager'; active:boolean; version:bigint}>
type Envelope = Readonly<{
  schemaVersion:1; dataVersion:string; freshUntil:number; staleUntil:number; value:Omit<Membership,'version'>|null
}>

const keyOf=(tenantId:string,userId:string)=>`prod:membership:v1:{${tenantId}}:${userId}`

function parseEnvelope(raw:string):Envelope {
  const x:unknown=JSON.parse(raw)
  if (!x || typeof x!=='object') throw new Error('BAD_CACHE')
  const r=x as Record<string,unknown>
  if (r.schemaVersion!==1 || typeof r.dataVersion!=='string' ||
      !/^(0|[1-9][0-9]*)$/.test(r.dataVersion) ||
      typeof r.freshUntil!=='number' || !Number.isFinite(r.freshUntil) ||
      typeof r.staleUntil!=='number' || !Number.isFinite(r.staleUntil) ||
      r.staleUntil<r.freshUntil) throw new Error('BAD_CACHE')
  if (r.value===null) return {schemaVersion:1,dataVersion:r.dataVersion,
    freshUntil:r.freshUntil,staleUntil:r.staleUntil,value:null}
  if (!r.value || typeof r.value!=='object') throw new Error('BAD_CACHE')
  const v=r.value as Record<string,unknown>
  if (typeof v.tenantId!=='string'||typeof v.userId!=='string'||
      (v.role!=='agent'&&v.role!=='manager')||typeof v.active!=='boolean') throw new Error('BAD_CACHE')
  return {schemaVersion:1,dataVersion:r.dataVersion,freshUntil:r.freshUntil,
    staleUntil:r.staleUntil,value:{tenantId:v.tenantId,userId:v.userId,role:v.role,active:v.active}}
}
```

只接受新 version 的 Lua：

```lua
-- KEYS[1]=cache key; ARGV[1]=incoming integer version; ARGV[2]=json; ARGV[3]=ttl ms
local function normalized(v)
  if not string.match(v,'^%d+$') then return nil end
  local n=string.gsub(v,'^0+','')
  return n=='' and '0' or n
end
local function greater(a,b)
  if string.len(a)~=string.len(b) then return string.len(a)>string.len(b) end
  return a>b
end
local incoming=normalized(ARGV[1])
if not incoming then return redis.error_reply('invalid version') end
local current=redis.call('HGET',KEYS[1],'version')
current=current and normalized(current) or nil
-- 只允许严格更高版本；同版本不同 payload 也不能覆盖已发布值。
if current and not greater(incoming,current) then
  return 0
end
redis.call('HSET', KEYS[1], 'version', incoming, 'json', ARGV[2])
redis.call('PEXPIRE', KEYS[1], ARGV[3])
return 1
```

脚本按规范化十进制字符串比较，因此不会把 PostgreSQL `bigint` 偷偷转成不安全的 Lua number。

核心 loader 把 singleflight 和 DB semaphore 注入：

```ts
interface Cache {get(key:string):Promise<string|null>; del(key:string):Promise<void>; putIfNewer(key:string,v:Envelope,ttlMs:number):Promise<boolean>}
interface MembershipDb {get(tenantId:string,userId:string):Promise<Membership|null>}
interface Gate {run<T>(fn:()=>Promise<T>):Promise<T>}

export class MembershipCache {
  private flights=new Map<string,Promise<Membership|null>>()
  constructor(private cache:Cache,private db:MembershipDb,private dbGate:Gate,
    private now:()=>number,private random:()=>number=Math.random){}

  async get(tenantId:string,userId:string,{securityCritical=false}={}) {
    const key=keyOf(tenantId,userId), now=this.now()
    try {
      const raw=await this.cache.get(key)
      if (raw) {
        const e=parseEnvelope(raw)
        if (e.value && (e.value.tenantId!==tenantId || e.value.userId!==userId)) throw new Error('CACHE_SCOPE_MISMATCH')
        const value=e.value ? {...e.value,version:BigInt(e.dataVersion)} : null
        if (now<e.freshUntil) return value
        if (!securityCritical && now<e.staleUntil) {
          void this.loadOnce(key,tenantId,userId).catch(()=>{})
          return value
        }
      }
    } catch {
      // 坏 envelope/错租户值必须清掉，否则伪造的超大 version 会阻止正确 DB 值回填。
      void this.cache.del(key).catch(()=>{})
    }
    return this.loadOnce(key,tenantId,userId)
  }

  private loadOnce(key:string,tenantId:string,userId:string) {
    const existing=this.flights.get(key)
    if (existing) return existing
    const promise=this.dbGate.run(async()=>{
      const row=await this.db.get(tenantId,userId), now=this.now()
      const ttl=row ? 60_000+Math.floor(this.random()*10_000) : 5_000
      const version=row?.version ?? 0n
      const value=row ? {tenantId:row.tenantId,userId:row.userId,role:row.role,active:row.active} : null
      await this.cache.putIfNewer(key,{schemaVersion:1,dataVersion:String(version),
        freshUntil:now+ttl,staleUntil:now+(row?5*60_000:ttl),value},row?5*60_000:ttl)
      return row
    }).finally(()=>this.flights.delete(key))
    this.flights.set(key,promise)
    return promise
  }
}
```

撤权路径：先提交 PostgreSQL version + active=false，再删除 key/发布带 version 的失效。安全读取 `securityCritical:true` 不返回 stale；若 Redis 与 DB 均不可用则拒绝高风险动作。

竞态测试使用 deferred promise：让旧 DB read 取得 v7 后暂停；提交 v8 并缓存；恢复 v7 的 put，断言 Lua 返回 0 且缓存仍 v8。

## 练习二答案：双 token bucket Lua

两个 key 必须处于同一 Cluster slot，例如：

```text
prod:rate:v2:{tenant-42}:tenant
prod:rate:v2:{tenant-42}:principal:user-7
```

```lua
-- KEYS: tenant, principal
-- ARGV: tenantCap, tenantRatePerMs, principalCap, principalRatePerMs, cost, ttlMs
local nowParts=redis.call('TIME')
local now=tonumber(nowParts[1])*1000+math.floor(tonumber(nowParts[2])/1000)
local cost=tonumber(ARGV[5])
if not cost or cost <= 0 then return redis.error_reply('invalid cost') end

local function peek(key, capacity, rate)
  local values=redis.call('HMGET',key,'tokens','at')
  local tokens=tonumber(values[1]) or capacity
  local at=tonumber(values[2]) or now
  local elapsed=math.max(0,now-at)
  return math.min(capacity,tokens+elapsed*rate)
end

local tenantCap,tenantRate=tonumber(ARGV[1]),tonumber(ARGV[2])
local userCap,userRate=tonumber(ARGV[3]),tonumber(ARGV[4])
local ttl=tonumber(ARGV[6])
if not tenantCap or not tenantRate or not userCap or not userRate or not ttl or
   tenantCap<=0 or tenantRate<=0 or userCap<=0 or userRate<=0 or ttl<=0 or
   tenantCap>1000000 or userCap>1000000 or ttl>86400000 then
  return redis.error_reply('invalid bucket config')
end
if cost>tenantCap or cost>userCap then return redis.error_reply('cost exceeds capacity') end
local tenant=peek(KEYS[1],tenantCap,tenantRate)
local user=peek(KEYS[2],userCap,userRate)

if tenant < cost or user < cost then
  local tenantWait=tenant < cost and math.ceil((cost-tenant)/tenantRate) or 0
  local userWait=user < cost and math.ceil((cost-user)/userRate) or 0
  return {0,math.floor(math.min(tenant,user)),math.max(tenantWait,userWait)}
end

tenant=tenant-cost; user=user-cost
redis.call('HSET',KEYS[1],'tokens',tenant,'at',now)
redis.call('HSET',KEYS[2],'tokens',user,'at',now)
redis.call('PEXPIRE',KEYS[1],ttl)
redis.call('PEXPIRE',KEYS[2],ttl)
return {1,math.floor(math.min(tenant,user)),0}
```

生产脚本还应验证 capacity/rate/ttl 上限且 rate > 0，避免除零与恶意超大参数；配置由服务端传，不让用户控制。若需要严格整数，统一使用 microtokens。

TypeScript adapter 只解释结果：

```ts
type LimitResult={allowed:boolean;remaining:number;retryAfterMs:number}
export async function limit(redis:RedisEval,keys:[string,string],args:readonly number[]):Promise<LimitResult>{
  const [ok,remaining,retry]=await redis.evalsha(scriptSha,keys,args)
  return {allowed:ok===1,remaining,retryAfterMs:retry}
}
```

Redis timeout 策略由 route risk 决定，不藏在通用 adapter：登录/退款返回 503 或本地极严 limiter；公共搜索进入有界本地 semaphore，超过即 429，不能无限打 DB。

## 常见错误

- 更新 DB 前先删除缓存；
- 用 Pub/Sub 当唯一失效保证；
- miss 时每个请求独立回源；
- 用 `SET NX` 锁却无 owner compare/fencing；
- 两个 bucket 分两次命令扣减；
- Redis 故障时所有流量无界回源。

## 复写验收

使用真实 Redis 8 跑 100 并发脚本，成功数不得超过 capacity；用 barrier 复现 v7 慢回填，最终必须为 v8。模拟 Redis 断线并断言 DB gate 并发上限未被突破。
