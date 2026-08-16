# 第 15 章答案

## 练习一答案：可测试的韧性客户端

先定义依赖，避免测试真实时间。fake clock 可精确推进 deadline 与 sleep：

```ts
type Outcome='success'|'retryable'|'permanent'|'unknown'
type Classified={outcome:Outcome;code:string;retryAfterMs?:number}
interface DeadlineHandle {signal:AbortSignal;dispose():void}
interface Clock {
  now():number
  sleep(ms:number,signal:AbortSignal):Promise<void>
  deadline(parent:AbortSignal,ms:number):DeadlineHandle
}
interface Transport {execute(req:RequestSpec,signal:AbortSignal):Promise<ResponseSpec>}
interface RetryBudget {tryTake(now:number):boolean;recordOriginal(now:number):void}
interface Classifier {response(x:ResponseSpec):Classified;error(x:unknown):Classified}
type RequestSpec={operation:string;idempotent:boolean;deadlineMs:number;operationId:string}
type ResponseSpec={status:number;body:unknown;headers:Readonly<Record<string,string>>}
```

真实 Node clock 要在每次 attempt 后释放 timer/listener：

```ts
export const systemClock:Clock={
  now:Date.now,
  sleep:(ms,signal)=>new Promise<void>((resolve,reject)=>{
    if(signal.aborted){reject(signal.reason);return}
    const timer=setTimeout(done,ms);timer.unref?.()
    const abort=()=>{clearTimeout(timer);cleanup();reject(signal.reason)}
    function cleanup(){signal.removeEventListener('abort',abort)}
    function done(){cleanup();resolve()}
    signal.addEventListener('abort',abort,{once:true})
  }),
  deadline(parent,ms){
    const controller=new AbortController()
    const abort=()=>controller.abort(parent.reason)
    if(parent.aborted) abort();else parent.addEventListener('abort',abort,{once:true})
    const timer=setTimeout(()=>controller.abort(tagged('DEADLINE_EXCEEDED','unknown')),ms)
    timer.unref?.()
    return {signal:controller.signal,dispose(){clearTimeout(timer);parent.removeEventListener('abort',abort)}}
  },
}
const fullJitter=(attempt:number,random:()=>number,base=100,cap=5_000)=>
  Math.floor(random()*Math.min(cap,base*2**attempt))
```

Node 24 也有 `AbortSignal.timeout/any`，但这个显式 handle 更容易验证生命周期。

Breaker：

```ts
export class CircuitBreaker {
  private state:'closed'|'open'|'half-open'='closed'
  private failures=0; private openedAt=0; private probe=false
  constructor(private threshold:number,private cooldownMs:number,private now:()=>number){}
  acquire(){
    if(this.state==='open' && this.now()-this.openedAt>=this.cooldownMs) this.state='half-open'
    if(this.state==='open') return false
    if(this.state==='half-open') {if(this.probe)return false;this.probe=true}
    return true
  }
  success(){this.failures=0;this.probe=false;this.state='closed'}
  abandonProbe(){if(this.state==='half-open')this.probe=false}
  failure(){
    this.probe=false;this.failures++
    if(this.state==='half-open'||this.failures>=this.threshold){this.state='open';this.openedAt=this.now()}
  }
  snapshot(){return {state:this.state,failures:this.failures}}
}
```

只对依赖故障调用 `failure()`，业务拒绝不改变 breaker。

```ts
export class ResilientClient {
  constructor(private transport:Transport,private clock:Clock,private random:()=>number,
    private budget:RetryBudget,private breaker:CircuitBreaker,private classifier:Classifier){}

  async execute(req:RequestSpec,parent:AbortSignal):Promise<ResponseSpec>{
    this.budget.recordOriginal(this.clock.now())
    let retryNumber=0
    while(true){
      if(parent.aborted) throw parent.reason
      const remaining=req.deadlineMs-this.clock.now()
      if(remaining<=50) throw tagged('DEADLINE_EXCEEDED','permanent')
      if(!this.breaker.acquire()) throw tagged('CIRCUIT_OPEN','retryable')
      const child=this.clock.deadline(parent,remaining-25)
      let result:{response?:ResponseSpec;error?:unknown;kind:Classified}
      try{
        const response=await this.transport.execute(req,child.signal)
        result={response,kind:this.classifier.response(response)}
      }catch(error){
        if(parent.aborted){this.breaker.abandonProbe();throw parent.reason}
        result={error,kind:this.classifier.error(error)}
      }finally{child.dispose()}

      const {kind}=result
      if(kind.outcome==='success'){
        if(!result.response){this.breaker.failure();throw tagged('CLASSIFIER_BUG','permanent')}
        this.breaker.success()
        return result.response
      }
      if(kind.outcome==='permanent'){
        // 明确 4xx 证明依赖可达；TLS/协议等永久 transport 错误仍是依赖失败。
        if(result.response)this.breaker.success();else this.breaker.failure()
        throw tagged(kind.code,'permanent')
      }
      if(kind.outcome==='retryable'||kind.outcome==='unknown') this.breaker.failure()
      if(kind.outcome==='unknown') throw tagged(kind.code,kind.outcome)
      if(!req.idempotent||!this.budget.tryTake(this.clock.now())) throw tagged(kind.code,'retryable')

      const wait=Math.min(kind.retryAfterMs??fullJitter(retryNumber++,this.random),5_000)
      if(this.clock.now()+wait+50>=req.deadlineMs) throw tagged('DEADLINE_EXCEEDED','permanent')
      await this.clock.sleep(wait,parent)
    }
  }
}

const tagged=(code:string,outcome:Outcome)=>Object.assign(new Error(code),{code,outcome})
```

单次 attempt 先归一化为 `result`，循环只在一个位置更新 breaker 和 retry，因此一次 503 不会被 try/catch 二次计数。

`Retry-After` 解析秒数或 HTTP date，拒绝 NaN/负数并 cap。写请求只有 provider 接受稳定 operation id 且明确返回“未执行”的错误才重试；断连/timeout 标记 UNKNOWN 并进入 reconciliation。

确定性测试用 fake clock 推进 sleep；random 固定序列；transport 脚本化返回。核心断言 attempt 次数、调用时间、breaker state、无遗留 timer/listener。

## 练习二答案：有界 Bulkhead

```ts
type Waiter={
  state:'queued'|'granted'|'cancelled'
  signal:AbortSignal
  resolve:(release:()=>void)=>void
  reject:(reason:unknown)=>void
  onAbort:()=>void
}

export class Bulkhead {
  private active=0
  private waiting:Waiter[]=[]
  constructor(private concurrency:number,private maxQueue:number){
    if(!Number.isInteger(concurrency)||concurrency<1||!Number.isInteger(maxQueue)||maxQueue<0)
      throw new RangeError('invalid bulkhead limits')
  }
  async run<T>(fn:()=>Promise<T>,signal:AbortSignal):Promise<T>{
    const release=await this.acquire(signal)
    if(signal.aborted){release();throw signal.reason}
    try{return await fn()}finally{release()}
  }
  private acquire(signal:AbortSignal):Promise<()=>void>{
    if(signal.aborted)return Promise.reject(signal.reason)
    if(this.active<this.concurrency){this.active++;return Promise.resolve(this.releaser())}
    if(this.waiting.length>=this.maxQueue)return Promise.reject(tagged('OVERLOADED','retryable'))
    return new Promise((resolve,reject)=>{
      const waiter={} as Waiter
      waiter.state='queued';waiter.signal=signal;waiter.resolve=resolve;waiter.reject=reject
      waiter.onAbort=()=>{
        if(waiter.state!=='queued')return
        waiter.state='cancelled'
        const index=this.waiting.indexOf(waiter);if(index>=0)this.waiting.splice(index,1)
        signal.removeEventListener('abort',waiter.onAbort)
        reject(signal.reason)
      }
      signal.addEventListener('abort',waiter.onAbort,{once:true})
      this.waiting.push(waiter)
    })
  }
  private releaser(){
    let released=false
    return ()=>{if(released)return;released=true;this.active--;this.grantNext()}
  }
  private grantNext(){
    while(this.active<this.concurrency){
      const waiter=this.waiting.shift();if(!waiter)return
      if(waiter.state!=='queued')continue
      waiter.state='granted';waiter.signal.removeEventListener('abort',waiter.onAbort)
      this.active++;waiter.resolve(this.releaser())
    }
  }
  stats(){return {active:this.active,queued:this.waiting.length}}
}
```

waiter 只允许 `queued -> granted|cancelled`，所有路径移除 listener；release 幂等。被 grant 后立刻 abort，`run` 的二次检查会释放 slot 而不执行工作。

组合顺序：入口大小/deadline/认证 → tenant limiter → global API bulkhead → cache → provider-specific bulkhead → resilient client。每层拒绝快速返回，不能进入下一层后再排队。

参数示例不是常量答案：若 provider 安全并发 80，预留后台/其他服务 20，则本服务 provider bulkhead 60；100 tenant 采用每 tenant 2 + 全局 60，有界队列 120。压测后按 provider P99、进程 heap 和 SLO 调整。

故障策略：

- public summary：存在未超过 staleUntil 的缓存则返回 `{data, freshness:'stale'}`；
- membership/refund：依赖不可用直接 503/fail closed；
- Redis 故障：本地全局 gate 仍保护 DB/provider；
- provider 恢复：half-open 1–3 探针，逐步把 concurrency 10%→25%→50%→100%，队列重试带 jitter。

指标：inflight/queued/shed（按有限 route/tenant tier）、queue wait、downstream latency、retry amplification、breaker state、deadline exceeded、stale served、provider saturation。告警看 SLO burn、shed 激增、queue wait、breaker 长开和恢复失败。

## 常见错误

- timeout 后把非幂等写当未执行；
- 每层各重试，形成乘法放大；
- breaker 把业务 400 计失败；
- 无界 Promise 队列；
- fallback 默认放过权限或返回假成功；
- provider 恢复瞬间释放全部积压；
- 只测平均延迟，不测 P99 和 shed。

## 复写验收

从空文件复写单次 attempt 结果状态机与 Bulkhead。用 10 秒慢 provider 压测，验证 inflight/queued 都不越界，小租户仍成功，恢复时下游 QPS 平滑增长。
