# 第 15 章答案：一条可答辩的生产证据链

> 这里给出的是可复写蓝图，不是一份可以冒充你项目的成品。你应真正运行测试、trace、canary 和事故演练，再用自己的数据替换示例。

## 题 1 参考答案：FlowOps Vertical Slice

### 1. 范围与架构决策

只做 tickets vertical slice；不做计费、组织管理、全功能富文本和微前端。使用 Nuxt 4 universal SSR 展示 request isolation，但 dashboard 返回 `private, no-store`；若团队只有两人且 SEO 无价值，可用 SPA，保留同样 BFF 授权与发布证据。

```text
route query (tenant/filter/page/ticket)
         ↓
TicketPage UI ─→ application use cases ─→ repository ports
   ↓ component state                         ↑
form/dialog/focus                 HTTP + realtime adapters
         ↓                                   ↓
design system                    Nitro BFF / trusted API
                                            ↓
                                  authz + schema + audit
```

状态表：

- URL：tenant、filter、page、selected ticket；
- server cache：list/detail/assignees，由 tenant+query key 标识；
- session state：公开 user/capabilities，不是服务端授权真相；
- local form：comment draft/submission；
- headless component：combobox open/query/active；
- application resource：realtime connection 与 event cursor。

ADR 记录拒绝“全 Pinia”：它会让 URL 导航、server stale time、form draft 和 overlay 生命周期共用错误更新语义。

### 2. Runtime schema 与领域映射

下面用伪 schema API 表达；实际可选成熟校验库：

```ts
interface TicketWire {
  id: string
  tenant_id: string
  title: string
  status: 'OPEN' | 'IN_PROGRESS' | 'CLOSED'
  assignee_id: string | null
  version: number
  updated_at: string
}

interface Ticket {
  id: string
  tenantId: string
  title: string
  status: 'open' | 'in_progress' | 'closed'
  assigneeId: string | null
  version: number
  updatedAtIso: string
}

export function parseTicket(value: unknown): Ticket {
  const wire = ticketWireSchema.parse(value) as TicketWire
  const status = {
    OPEN: 'open',
    IN_PROGRESS: 'in_progress',
    CLOSED: 'closed',
  } as const
  if (!Number.isSafeInteger(wire.version) || wire.version < 0) {
    throw new Error('Invalid ticket version')
  }
  return {
    id: wire.id,
    tenantId: wire.tenant_id,
    title: wire.title,
    status: status[wire.status],
    assigneeId: wire.assignee_id,
    version: wire.version,
    updatedAtIso: new Date(wire.updated_at).toISOString(),
  }
}
```

HTTP adapter 将 transport 转判别联合：

```ts
type AssignResult =
  | { type: 'assigned'; ticket: Ticket }
  | { type: 'conflict'; current: Ticket }
  | { type: 'forbidden' }
  | { type: 'unavailable'; retryable: boolean }

async function assignTicket(input: {
  ticketId: string
  assigneeId: string
  baseVersion: number
  idempotencyKey: string
}): Promise<AssignResult> {
  const response = await fetch(`/api/tickets/${encodeURIComponent(input.ticketId)}/assignee`, {
    method: 'PUT',
    headers: {
      'content-type': 'application/json',
      'idempotency-key': input.idempotencyKey,
    },
    body: JSON.stringify({
      assigneeId: input.assigneeId,
      baseVersion: input.baseVersion,
    }),
  })
  if (response.status === 409) {
    return { type: 'conflict', current: parseTicket(await response.json()) }
  }
  if (response.status === 403 || response.status === 404) return { type: 'forbidden' }
  if (!response.ok) return { type: 'unavailable', retryable: response.status >= 500 }
  return { type: 'assigned', ticket: parseTicket(await response.json()) }
}
```

服务端跨 tenant 可返回 404 以减少对象存在性泄露，具体由安全策略决定。前端不能通过改 `tenantId` 获得能力。

### 3. 查询竞态与 cache identity

```ts
export function useTicketSearch(repository: TicketRepository) {
  const state = shallowRef<
    | { type: 'idle' }
    | { type: 'loading'; previous?: TicketPage }
    | { type: 'ready'; page: TicketPage }
    | { type: 'error'; retryable: boolean }
  >({ type: 'idle' })
  let generation = 0
  let aborter: AbortController | undefined

  async function run(query: TicketQuery): Promise<void> {
    const own = ++generation
    aborter?.abort()
    aborter = new AbortController()
    const previous = state.value.type === 'ready' ? state.value.page : undefined
    state.value = { type: 'loading', previous }
    try {
      const page = await repository.list(query, aborter.signal)
      if (own !== generation || aborter.signal.aborted) return
      state.value = { type: 'ready', page }
    } catch (error: unknown) {
      if (own !== generation || aborter.signal.aborted) return
      state.value = { type: 'error', retryable: isRetryable(error) }
    }
  }

  function stop(): void {
    generation += 1
    aborter?.abort()
  }

  onScopeDispose(stop)
  return { state, run, stop }
}
```

Nuxt/server-state key 示例：`tickets:${tenantId}:${stableQueryHash(filter,page,sort)}`。hash 输入须 canonical、无随机值、无敏感高基数字段；不同 tenant 永不共 key。Abort 减少浪费，generation 防旧结果提交。

### 4. Conflict 与幂等评论

分配采用 hybrid：立即把按钮置 pending，保留服务器确认的 assignee。结果为：

```ts
async function submitAssignment(assigneeId: string): Promise<void> {
  if (assignState.value.type === 'submitting') return
  const base = ticket.value
  assignState.value = { type: 'submitting', targetId: assigneeId }
  const result = await repository.assign({
    ticketId: base.id,
    assigneeId,
    baseVersion: base.version,
    idempotencyKey: crypto.randomUUID(),
  })
  if (result.type === 'assigned') {
    ticket.value = result.ticket
    updateListEntity(result.ticket)
    assignState.value = { type: 'idle' }
  } else if (result.type === 'conflict') {
    ticket.value = result.current
    assignState.value = { type: 'conflict', current: result.current }
  } else if (result.type === 'forbidden') {
    assignState.value = { type: 'forbidden' }
  } else {
    assignState.value = { type: 'failed', retryable: result.retryable }
  }
}
```

评论在用户第一次提交时生成 `clientCommentId/idempotencyKey`，超时重试复用同一 key。服务器在 tenant+user+key 范围存命令结果并返回同一 comment；客户端用 server id/client id 去重。生成新 key 重试会重复，UI 必须把 key 绑在 pending draft 上。

### 5. Realtime reducer

```ts
interface TicketChanged {
  eventId: string
  ticketId: string
  tenantId: string
  entityVersion: number
  patch: Partial<Pick<Ticket, 'status' | 'assigneeId' | 'updatedAtIso'>>
}

function applyTicketEvent(current: Ticket, event: TicketChanged):
  | { type: 'ignored'; reason: 'duplicate-or-old' | 'wrong-entity' }
  | { type: 'applied'; ticket: Ticket }
  | { type: 'gap' } {
  if (event.ticketId !== current.id || event.tenantId !== current.tenantId) {
    return { type: 'ignored', reason: 'wrong-entity' }
  }
  if (event.entityVersion <= current.version) {
    return { type: 'ignored', reason: 'duplicate-or-old' }
  }
  if (event.entityVersion !== current.version + 1) return { type: 'gap' }
  return {
    type: 'applied',
    ticket: { ...current, ...event.patch, version: event.entityVersion },
  }
}
```

eventId 用有上限 LRU/last cursor 去重；gap 标 cache stale 并 refetch。socket owner 负责指数退避+jitter、online/visibility、logout/tenant switch cleanup，不让每个 row 建连接。

### 6. UI 与 a11y 证据

- 筛选器用真实 label，URL 更新 debounce 且 back/forward 恢复；
- 工单列表只读时用 table + server pagination，10k 行不必虚拟化；若连续滚动需求成立才选窗口化并提供分页/打印路径；
- assignee 使用第 13 章 combobox 状态机；input focus、active descendant、disabled、IME、loading/error；
- conflict 是页面内可恢复区域，显示当前 assignee/version，焦点移到标题或提示并可刷新/重新选择；
- 评论 error 贴近表单，保留 draft，`aria-live` 只宣布有意义结果；
- viewer 根本没有可操作控件，但即使手工调用 API 也被服务端拒绝。

### 7. 测试最小集合

**Unit/property**：wire mapper、permission projection、event reducer 的 duplicate/old/gap、query canonicalization、money/time。

**Composable**：A 慢 B 快；abort 抛错不显示 error；unmount 后不提交；assign single-flight；comment retry 复用 key。

**Component**：键盘筛选/combobox/comment；loading/empty/error/conflict；role/name/state；外部 model update。

**Integration**：router query ↔ search key ↔ cache；mutation 更新 detail/list、统计失效；401 刷新/登出并发。

**E2E**：agent 完整旅程；manager 先改造成 409；viewer/cross-tenant 篡改失败；offline/reconnect；async chunk error。

**SSR**：A/B barrier 并发 HTML/payload；hydrate 零 warning；首次 API 不重复；401/404/status/header；恶意 payload 序列化；private/no-store。

**Performance/memory**：10k fixture 下 DOM、INP、更新数；route 20 次进入退出后的 socket/listener/heap 平台；initial chunk 中无 editor/chart。

### 8. 发布与证据

PR gates：lint/type/schema boundary、unit/component/integration、SSR smoke、bundle diff、a11y smoke。构建一次 immutable artifact，部署 staging 后跑 E2E/perf/security；按内部→1%租户→10%→全量 rollout。flag 控制新 tickets UI，服务器 API 向后兼容旧 tab。

release dashboard：`ticket_list_ready`、assign success/conflict/error、comment retry/dedup、LCP/INP、JS error、API status、socket reconnect，全部按 release/flag/route 分段。阈值恶化或任何跨租户访问立即 stop/rollback。

Runbook：如何关闭 flag、pin artifact、purge 哪些公共缓存（dashboard 本不应 public）、验证 API/旧 tab、检查重复命令和通知安全负责人。

### 9. 两份 ADR 示例结论

1. **状态策略**：URL + server cache + local form + session store 分治；拒绝全 Pinia。代价是层次更多，需要 key/owner 文档；当项目缩成单页且无分享导航时重审。
2. **表格策略**：server pagination + 原生 table；拒绝默认虚拟 10k DOM。原因是可访问、打印和后端已有查询；当明确连续滚动且分页任务失败时再评估 virtualization。

### 10. 规模缩小十倍

可删除复杂 realtime gap recovery（改短轮询）、独立 RUM pipeline（保留基础错误/业务指标）、多阶段 remote/微前端、复杂虚拟化、完整平台化 schema generator。仍保留服务端对象授权、schema、幂等命令、竞态 cleanup、关键路径测试、可访问表单、私有缓存和可回滚制品。这些是正确性/安全不变量，不由规模豁免。

## 题 2 参考答案：事故演练与答辩

### 1. 前 15 分钟

跨租户泄漏优先级高于性能：

**0–3 分钟**：值班者宣布安全 incident，指定 commander/记录者（人少可兼任），冻结发布；确认 release/flag/CDN route，不在群里转发敏感 HTML。

**3–7 分钟**：关闭新 dashboard flag 或 pin 上一安全 artifact；立刻将个性化 HTML/API 改为 bypass/private/no-store 并 purge 相关 CDN keys；若模块 singleton 已进入所有实例，滚回并替换/restart worker。保留出错 HTML、headers、request/release/trace、CDN cache status 与访问日志的受控副本。

**7–12 分钟**：验证两个测试租户并发请求不串；检查可能受影响时间窗口、cache POP/key/release；撤销可能泄漏的会话/凭证（payload 本不应含 secret）；通知安全/法务/产品按预案评估外部通知。

**12–15 分钟**：确认错误率、跨租户 sentinel 和 cache hit 已恢复；性能回归通过 rollback 同时缓解。另开重复 assign 数据调查，不清库；冻结 event schema rollout/强制兼容。

若只有一人：先执行预批准的 kill switch/rollback + CDN bypass，保留自动时间线，然后按 on-call escalation 呼叫安全/平台；不要同时深入 heap、性能和 schema。

### 2. Timeline 示例

```text
10:00 release R2026.09.01 canary 10%
10:08 dashboard LCP alert（只有全局维度，未自动回滚）
10:13 first cross-tenant support report
10:15 incident declared / rollout frozen
10:18 feature flag off, CDN bypass rule applied
10:21 previous artifact pinned, purge started
10:27 two-tenant concurrency sentinel passes
10:35 affected cache keys/time range identified
10:48 duplicate assign audit begins; event v2 stopped
11:10 service stable; monitoring window starts
```

真实复盘只写证据，不虚构分钟。影响需用访问日志/CDN key/tenant/request 定界；若无法排除数据被他人看见，按安全流程使用保守上界。重复命令通过 idempotency/audit 记录修复业务数据，通知条件由组织 incident policy 与法规决定。

### 3. Root cause tree

```text
Trigger
├─ module-level tenant ref in SSR
├─ CDN public cache on personalized HTML
├─ unstable row props + sync chart import
├─ KeepAlive resources missing deactivate cleanup
├─ retry without server idempotency enforcement
└─ breaking event schema without compatibility window

Latent conditions
├─ no concurrent-tenant SSR test
├─ cache defaults not deny-by-default
├─ no bundle/update budget
├─ no resource ownership template/test
├─ API contract allowed old clients to disappear instantly
└─ release combined six independent risks

Amplifiers
├─ CDN global POPs
├─ long-lived old tabs
├─ canary lacked tenant isolation sentinel
└─ monitoring lacked tenant/release/cache-status slice

Detection gaps
├─ performance alert came before security but no correlation
├─ no cross-tenant synthetic
└─ logs insufficiently linked yet must avoid raw tenant PII
```

根因不是“某人用了 ref”，而是共享状态和公共缓存两层安全失败能同时发布且无测试/默认护栏。

### 4. 最小恢复与长期 actions

| Action | 类型 | 验证 |
| --- | --- | --- |
| rollback + flag off + CDN bypass/purge | immediate | 两 tenant 并发/多 POP/header 检查 |
| 每请求 `useState`/app context，删除模块 user state | code | barrier concurrency test + hydrate test |
| personalized route 强制 `private,no-store`，CDN policy deny | platform | CI/config policy + integration |
| 服务端 idempotency ledger + reconciliation | correctness | 相同 key 多次/响应丢失测试 |
| event N/N-1 schema + version parser | compatibility | old/new tab matrix |
| chart async boundary、stable props、pagination/profile | performance | before/after trace + RUM |
| resource owner start/stop + deactivate test | memory | 20 循环 heap/listener/socket plateau |
| 拆分 risky release、canary sentinel | delivery | release drill |

每项必须填真实 owner/日期。三条可执行 guardrail 可以是：

1. 架构 lint 禁止 server request state 的模块顶层 `ref/reactive`（加人工审查豁免）；
2. CDN policy-as-code：匹配 dashboard/session cookie 的响应若 public cache 直接阻断部署；
3. CI 每次用两个并发 tenant + malicious payload 做 SSR/cache isolation，并跑 old/new contract matrix。

再加 bundle/update budget 与 lifecycle resource counters，可覆盖其余故障。

### 5. 回滚后验证

- 多 CDN POP/冷暖 cache 请求 A/B；`Age`, cache status, cache-control 正确；
- 所有 server process 使用旧/修复 release，内存中旧 singleton 不再服务；
- payload/HTML/log/source map 无其他 tenant/secret；
- old tab 的 v1 event/assign API 仍工作，新 event 暂停或兼容；
- 相同 idempotency key 多次提交只产生一次业务事实；对事故窗口用审计账本对账；
- 10k fixture 的 LCP/INP/initial JS 恢复预算；
- 20 次 KeepAlive 循环资源归零/稳定；
- 安全 sentinel、错误、API、业务成功率持续稳定一个批准窗口。

### 6. Postmortem 的反事实

若只有“每请求状态”护栏，CDN public cache 仍可串用户；若只有 private cache，singleton 仍可能在同一进程并发请求间串值。两道防线都要修复。若服务端严格幂等，即便客户端 timeout retry 也不会重复业务事实。这些反事实帮助 action 针对系统而不是个人。

### 7. 15 分钟答辩结构

1. 1 分钟：用户/规模/不变量/非目标；
2. 3 分钟：架构图与状态 owner；
3. 3 分钟：一条请求 + mutation conflict + realtime gap；
4. 2 分钟：a11y/security/SSR trust boundary；
5. 2 分钟：风险驱动测试；
6. 2 分钟：performance before/after（环境、p75、trace）；
7. 1 分钟：release/canary/rollback；
8. 1 分钟：最差取舍与下一步。

### 8. 十个追问的回答骨架

**为什么不全 Pinia？** URL、remote cache、form、overlay 的 identity/lifecycle/staleness 不同；按 owner 分治，Pinia 只承担合适 session/client state。

**abort 后为何 generation？** 某些 adapter/已完成 response 不保证 abort 阻止 resolve；generation 是提交正确性，abort 是资源优化。

**409 与 optimistic？** 高冲突操作用 hybrid 或带 snapshot/version 的 optimistic；409 以 current representation 重建，不能静默 last-write-wins。

**SSR isolation 如何测？** barrier 让 A/B 写入和 await 交错，断言 HTML/payload/cache；真实浏览器 hydrate；不是串行跑两个请求。

**guard 为何不是授权？** 浏览器由用户控制；route/button 只优化 UX，服务端必须基于可信 session 对每个对象授权。

**虚拟化/分页/`v-memo` 顺序？** 先 trace：后端与产品允许时 server pagination 降低总数据；大 DOM 再虚拟化；不稳定 props 先修；`v-memo` 仅在剩余 render hotspot 且失效协议可靠时。

**unit mock 不能证明什么？** 真实浏览器 focus/layout/Teleport/IME、cookie/CSRF、hydration、CDN、第三方 SDK 内存和网络组合。

**为什么不微前端/Vapor？** 当前单团队单切片无独立部署证据；微前端成本不值。生产基线 Vue3.5；3.6 RC/Vapor 是 opt-in API 子集的隔离实验，不能混入高风险迁移。

**旧 tab/回滚？** API/event N/N-1、expand-contract、immutable artifact、flag、server 不要求最新 JS；回滚先兼容数据/schema。

**三个取舍？** SSR 增 server/hydration 复杂度；server pagination 牺牲连续滚动；hybrid mutation 反馈不如盲 optimistic 即时。若 RUM/成本、用户任务和 conflict 数据变化，就重审。

答辩数字示例应说：“在固定 Moto G 类 CPU/4G、10k fixture、冷 cache 下，20 次中位/分位；灰度真实移动 p75 从 X 到 Y，样本 N；release/flag 分段。”不能只说“快了 40%”。

## 毕业复写检查

在不看答案时完成以下内容才算过关：

1. 一张状态 owner + trust boundary 图；
2. wire schema → domain → repository → UI 的关键代码；
3. abort/generation、409、idempotency、event gap 四个失败协议；
4. 风险到测试层的映射；
5. 性能、SSR、内存的 evidence 方法；
6. canary/old-tab/rollback/runbook；
7. 15 分钟项目陈述；
8. 一份不归咎个人、有可执行 guardrail 的 postmortem。
