# 第 20 章答案：用所有权、取消与请求隔离贯通 Vue 生态源码

> 参考实现展示关键不变量，不替代第 05、06、07、12、13 章的完整组件与 SSR 工程。生产项目还需接入真实鉴权、日志脱敏、CSP、监控和框架适配层。

## 练习 1 参考答案：可缓存工单页与异步 Overlay 工作台

### 1. 先画所有权表

| 资源 | owner | active 时 | deactivated 时 | unmounted 时 |
| --- | --- | --- | --- | --- |
| 草稿 | ticket id 对应页面实例，或专用 draft store | 可编辑 | 保留 | 根据产品决定持久化/丢弃 |
| 轮询 timer | active TicketPage | 运行 | 停止 | 停止并释放 |
| 当前 fetch | 本轮 polling generation | 可完成 | abort + 作废 generation | abort + 作废 |
| Modal focus trap | topmost overlay | 运行 | 不适用 | cleanup + restore focus |
| body scroll lock | overlay manager 引用计数 | +1 | 不适用 | -1，归零才解锁 |
| async loader 结果 | ticketId + requestId | 可提交 | 若 UI 关闭/换票则不得提交 | 不得提交 |
| KeepAlive cache | KeepAlive 实例 | active/缓存 | 保留 | parent unmount 时清空 |

这张表比“在 onUnmounted 里 clearInterval”更可靠，因为 KeepAlive 的页面离开并不 unmount。

### 2. `max=2` 的手算结果

Map 保存 VNode，Set 用删除再添加维护新鲜度。序列：

| 导航 | 事件 | keys 从旧到新 | 淘汰 |
| --- | --- | --- | --- |
| A | mount A | `[A]` | 无 |
| B | deactivate A，mount B | `[A,B]` | 无 |
| A | deactivate B，activate A | `[B,A]` | 无 |
| C | deactivate A，mount C | `[B,A,C] → [A,C]` | B 真正 unmount |
| B | deactivate C，mount 新 B | `[A,C,B] → [C,B]` | A 真正 unmount |

最终 B active、C cached/deactivated。第一次 B 的局部实例已经被淘汰，所以最后 B 是新实例。若业务要求 B 草稿仍在，`max=2` 与该产品需求冲突；应提高预算或把草稿移到以 ticket id 索引的持久 owner。

### 3. 幂等 polling composable

下面示例使用注入 clock，便于测试；真实 loader 还应有超时、认证错误和 backoff 策略。

```ts
import {
  onActivated,
  onBeforeUnmount,
  onDeactivated,
  onMounted,
  readonly,
  ref,
  toValue,
  type MaybeRefOrGetter,
  type Ref,
} from 'vue'

export interface Clock {
  setInterval(callback: () => void, ms: number): unknown
  clearInterval(handle: unknown): void
}

export interface TicketStatus {
  id: string
  revision: number
  state: 'open' | 'pending' | 'closed'
}

export type TicketStatusLoader = (
  ticketId: string,
  signal: AbortSignal,
) => Promise<TicketStatus>

export interface TicketPolling {
  status: Readonly<Ref<TicketStatus | null>>
  error: Readonly<Ref<Error | null>>
  refresh(): Promise<void>
}

export function useTicketPolling(
  ticketId: MaybeRefOrGetter<string>,
  load: TicketStatusLoader,
  clock: Clock = {
    setInterval: (callback, ms) => window.setInterval(callback, ms),
    clearInterval: handle => window.clearInterval(handle as number),
  },
): TicketPolling {
  const status = ref<TicketStatus | null>(null)
  const error = ref<Error | null>(null)
  let timer: unknown | undefined
  let currentController: AbortController | undefined
  let generation = 0
  let active = false

  async function refresh(): Promise<void> {
    if (!active) return
    const id = toValue(ticketId)
    const myGeneration = generation

    currentController?.abort('superseded poll')
    const controller = new AbortController()
    currentController = controller

    try {
      const next = await load(id, controller.signal)
      if (
        active &&
        !controller.signal.aborted &&
        myGeneration === generation &&
        id === toValue(ticketId)
      ) {
        status.value = next
        error.value = null
      }
    } catch (cause) {
      if (
        active &&
        !controller.signal.aborted &&
        myGeneration === generation
      ) {
        error.value = cause instanceof Error ? cause : new Error(String(cause))
      }
    } finally {
      if (currentController === controller) currentController = undefined
    }
  }

  function start(): void {
    if (active) return // mounted + activated 都调用也不会双启动
    active = true
    generation += 1
    void refresh()
    timer = clock.setInterval(() => void refresh(), 5_000)
  }

  function stop(reason: string): void {
    if (!active && timer === undefined && !currentController) return
    active = false
    generation += 1
    currentController?.abort(reason)
    currentController = undefined
    if (timer !== undefined) {
      clock.clearInterval(timer)
      timer = undefined
    }
  }

  onMounted(start)
  onActivated(start)
  onDeactivated(() => stop('component deactivated'))
  onBeforeUnmount(() => stop('component unmounted'))

  return { status: readonly(status), error: readonly(error), refresh }
}
```

为什么同时注册 mounted 与 activated？组件可能不在 KeepAlive 中复用。KeepAlive 首次挂载还可能触发 activated；`start()` 的幂等判断是关键，而不是赌某个 hook 只调用一次。

#### 必要测试

```ts
it('does not commit a late response after deactivation', async () => {
  // 1. mount A，loader 返回 deferred promise
  // 2. 触发 deactivated
  // 3. resolve deferred
  // 4. flush promises
  // 5. status 仍未被旧结果写入，signal.aborted === true
})

it('owns exactly one interval across initial activation', () => {
  // 使用 fake timers / injected clock 统计 active handles，必须为 1
})

it('fully releases work when LRU eviction unmounts the page', () => {
  // A→B→A→C，断言 B 的 abort、clearInterval、unmount 各一次
})
```

不要只断言 `clearInterval` 被调用；还要断言旧 Promise 即使不响应 abort，也因 generation 失效不能 commit。

### 4. Async panel 状态机

```ts
import { readonly, ref, type Ref } from 'vue'

type PanelState<T> =
  | { tag: 'idle' }
  | { tag: 'pending'; requestId: string; ticketId: string }
  | { tag: 'ready'; requestId: string; ticketId: string; value: T }
  | { tag: 'failed'; requestId: string; ticketId: string; error: Error }

export interface PanelController<T> {
  state: Readonly<Ref<PanelState<T>>>
  open(ticketId: string): Promise<void>
  close(): void
}

export function createPanelController<T>(
  loader: (ticketId: string, signal: AbortSignal) => Promise<T>,
): PanelController<T> {
  const state = ref<PanelState<T>>({ tag: 'idle' })
  let sequence = 0
  let controller: AbortController | undefined

  async function open(ticketId: string): Promise<void> {
    controller?.abort('new panel request')
    controller = new AbortController()
    const local = controller
    const requestId = `${ticketId}:${++sequence}`
    state.value = { tag: 'pending', ticketId, requestId }

    try {
      const value = await loader(ticketId, local.signal)
      if (
        !local.signal.aborted &&
        state.value.tag === 'pending' &&
        state.value.requestId === requestId
      ) {
        state.value = { tag: 'ready', ticketId, requestId, value }
      }
    } catch (cause) {
      if (
        !local.signal.aborted &&
        state.value.tag === 'pending' &&
        state.value.requestId === requestId
      ) {
        state.value = {
          tag: 'failed',
          ticketId,
          requestId,
          error: cause instanceof Error ? cause : new Error(String(cause)),
        }
      }
    }
  }

  function close(): void {
    controller?.abort('panel closed')
    controller = undefined
    sequence += 1
    state.value = { tag: 'idle' }
  }

  return { state: readonly(state), open, close }
}
```

这个 controller 管理业务数据加载；`defineAsyncComponent` 管理代码 chunk 加载。两种 async 不应混成一个 `isLoading`：chunk 可能已缓存，但 ticket data 每次不同。

### 5. `defineAsyncComponent` 策略

```ts
import { defineAsyncComponent } from 'vue'
import AuditChunkError from './AuditChunkError.vue'
import AuditChunkLoading from './AuditChunkLoading.vue'

function isRetryableChunkFailure(error: unknown): boolean {
  return error instanceof TypeError ||
    (error instanceof Error && /fetch|network|chunk/i.test(error.message))
}

export const AsyncAuditPanel = defineAsyncComponent({
  loader: () => import('./AuditPanel.vue'),
  delay: 150,
  timeout: 10_000,
  loadingComponent: AuditChunkLoading,
  errorComponent: AuditChunkError,
  onError(error, retry, fail, attempts) {
    if (isRetryableChunkFailure(error) && attempts < 2) retry()
    else fail()
  },
})
```

`attempts < 2` 表示最多第二次尝试；实际策略需对离线、部署版本错配、CSP 和真实代码错误分类。不要遇到任意异常就 reload 页面。

### 6. Suspense 与错误边界

一个最小 error boundary：

```vue
<script setup lang="ts">
import { onErrorCaptured, ref } from 'vue'

const error = ref<Error | null>(null)

function reset(): void {
  error.value = null
}

onErrorCaptured(cause => {
  error.value = cause instanceof Error ? cause : new Error(String(cause))
  return false // 已处理；按产品策略决定是否继续传播
})
</script>

<template>
  <slot v-if="!error" />
  <section v-else role="alert">
    <p>审计面板加载失败。</p>
    <button type="button" @click="reset">重试</button>
  </section>
</template>
```

真实重试还要换 async child key 或调用 controller/open，不能只清 error 后复用一个永久 rejected 状态。

由于 Suspense 仍 experimental，ADR 应写：

- 使用范围仅审计次级面板；
- loading/error 的业务状态独立；
- 无 Suspense 时 AsyncAuditPanel 自己仍有 loading/error component；
- 版本升级跑 resolve/reject/navigation-away 回归；
- 关闭 feature flag 可以退回显式状态。

### 7. Teleport Dialog 验收重点

第 13 章已有完整 overlay/combobox 设计。本题至少应证明：

```ts
const target = document.createElement('div')
target.id = 'overlays'
document.body.append(target)

const wrapper = mount(Workbench, { attachTo: document.body })
await wrapper.get('[data-open-audit]').trigger('click')

const dialog = document.querySelector<HTMLElement>('#overlays [role="dialog"]')
expect(dialog).not.toBeNull()
expect(dialog?.getAttribute('aria-modal')).toBe('true')
expect(dialog?.contains(document.activeElement)).toBe(true)

wrapper.unmount()
target.remove()
```

组件测试之外用 Playwright 验证 Tab 循环、Shift+Tab、Escape、嵌套 topmost 和触发器 focus restore。scroll lock 应由共享 manager 计数：

```text
open A: count 0→1，lock
open B: count 1→2，不重复修改原 style
close B: count 2→1，保持 lock
close A: count 1→0，恢复原 style
```

target 缺失时可以 fail fast（开发和测试最清楚），或在统一 OverlayHost 中保证 target 先存在。不要让每个 Modal 私自往 body 创建同名节点。

### 8. 源码审计结论

| 结论 | v3.5.42 实现证据 | public 依赖方式 |
| --- | --- | --- |
| KeepAlive 复用实例 | Map cache + VNode component/el 复用 | key、include/exclude/max、activated hooks |
| LRU-like max | Set 命中时 delete/add，超限删最旧 | 只依赖 max 语义，不读内部 Set |
| deactivate 非 unmount | move 到 storage container | 同时实现 deactivated/unmounted cleanup |
| Teleport 双位置 | main placeholders + target anchors | `to`、`disabled`、`defer` 文档语义 |
| async loader 去重 | pendingRequest / resolvedComp | `defineAsyncComponent` options |
| Suspense 缓冲 | pendingBranch/deps/effects | 只在批准版本与回退策略下使用 |

---

## 练习 2 参考答案：Router + Pinia 并发导航与 SSR 隔离证明

### 1. 先定义请求级边界

```text
process-global：编译后的 route definitions、纯函数 schema、无状态 service factories
request-local：app、router、pinia、stores、session、AbortController、SSR context
user/session-shared：只能通过有 tenant/user key 的后端存储或明确 cache 协议
```

“Node 单线程”不能使 request-local 变 global。两个请求在 `await` 处分时交错，模块单例仍会串数据。

### 2. Store 定义可以全局，Store 实例不可以

```ts
import { defineStore } from 'pinia'

export interface PublicUser {
  id: string
  displayName: string
  tenantId: string
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as PublicUser | null,
    // token 故意不进入可序列化 client store
  }),
  getters: {
    isAuthenticated: state => state.user !== null,
  },
})
```

模块级 `useAuthStore` 是 definition/factory；危险的是模块顶层执行 `useAuthStore()` 并持有结果。

### 3. 每请求 app 工厂

```ts
import { createSSRApp, type App as VueApp } from 'vue'
import {
  createMemoryHistory,
  createRouter,
  type Router,
  type RouteRecordRaw,
} from 'vue-router'
import { createPinia, type Pinia } from 'pinia'
import Root from './Root.vue'

export interface RequestApp {
  app: VueApp
  router: Router
  pinia: Pinia
}

const routes: readonly RouteRecordRaw[] = [
  {
    path: '/:tenantId/tickets/:ticketId',
    name: 'ticket',
    component: () => import('./TicketRoute.vue'),
    meta: { requiresAuth: true },
  },
  { path: '/not-found', name: 'not-found', component: NotFoundRoute },
]

export function createRequestApp(): RequestApp {
  const app = createSSRApp(Root)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [...routes],
  })
  const pinia = createPinia()

  app.use(pinia)
  app.use(router)

  return { app, router, pinia }
}
```

`routes` definitions 可复用，但 router/matcher/currentRoute/history state 每请求新建。若动态 addRoute 随 tenant 变化，连 route records 的生成也应请求级或按不可变配置缓存。

### 4. Guard 显式接收 Pinia 与服务

```ts
import type { Pinia } from 'pinia'
import type { Router } from 'vue-router'
import { z } from 'zod'

const Segment = z.string().min(1).max(100).regex(/^[a-zA-Z0-9_-]+$/)

export interface GuardServices {
  isTenantAllowed(userId: string, tenantId: string): Promise<boolean>
}

export function installGuards(
  router: Router,
  pinia: Pinia,
  services: GuardServices,
): void {
  router.beforeEach(async to => {
    const auth = useAuthStore(pinia)
    if (to.meta.requiresAuth && !auth.user) {
      return { name: 'login', query: { redirect: to.fullPath } }
    }

    const tenant = Segment.safeParse(to.params.tenantId)
    const ticket = Segment.safeParse(to.params.ticketId)
    if (!tenant.success || !ticket.success) return { name: 'not-found' }
    if (!auth.user) return true

    const allowed = await services.isTenantAllowed(auth.user.id, tenant.data)
    return allowed ? true : { name: 'forbidden' }
  })
}
```

服务端最终还必须在 API/数据库层验证 tenant authorization。前端/SSR route guard 不是唯一安全边界。

### 5. 安全序列化只选择公开 state

```ts
export function serializeForHtml(value: unknown): string {
  return JSON.stringify(value)
    .replace(/</g, '\\u003c')
    .replace(/\u2028/g, '\\u2028')
    .replace(/\u2029/g, '\\u2029')
}

function selectPublicState(pinia: Pinia): unknown {
  const auth = useAuthStore(pinia)
  return {
    auth: {
      user: auth.user && {
        id: auth.user.id,
        displayName: auth.user.displayName,
        tenantId: auth.user.tenantId,
      },
    },
  }
}
```

不要先把 token 放进 Pinia 再靠 replacer 黑名单删除；白名单选择公开 hydration state 更可靠。实际项目可使用框架推荐 serializer，并配 CSP nonce/外部 payload。

### 6. `renderRequest`

```ts
import { renderToString } from '@vue/server-renderer'

export interface Session {
  user: PublicUser
  token: string // 只传给 server service，不写 Pinia hydration
}

export async function renderRequest(input: {
  url: string
  session: Session
  services: GuardServices
}): Promise<{ html: string; state: string }> {
  const { app, router, pinia } = createRequestApp()
  const auth = useAuthStore(pinia)
  auth.user = input.session.user

  installGuards(router, pinia, input.services)
  await router.push(input.url)
  await router.isReady()

  const html = await renderToString(app)
  const state = serializeForHtml(selectPublicState(pinia))

  return { html, state }
}
```

若 action/service 需要 token，把它留在 request context 或 server-only client 中；不要挂到会序列化的 store。渲染失败时也应 abort 请求级 loaders，并让日志带 request id/tenant id 但不带 token。

### 7. Route Load Coordinator

```ts
export interface RouteLoadKey {
  tenantId: string
  ticketId: string
}

export type TicketLoader<T> = (
  key: RouteLoadKey,
  signal: AbortSignal,
) => Promise<T>

export class StaleRouteLoadError extends Error {
  constructor(message = 'Route load became stale') {
    super(message)
    this.name = 'StaleRouteLoadError'
  }
}

function keyOf(key: RouteLoadKey): string {
  return `${encodeURIComponent(key.tenantId)}:${encodeURIComponent(key.ticketId)}`
}

export class DefaultRouteLoadCoordinator<T> {
  private generation = 0
  private disposed = false
  private current:
    | {
        key: string
        generation: number
        controller: AbortController
        promise: Promise<T>
      }
    | undefined

  constructor(private readonly loader: TicketLoader<T>) {}

  load(key: RouteLoadKey): Promise<T> {
    if (this.disposed) {
      return Promise.reject(new Error('RouteLoadCoordinator is disposed'))
    }

    const serialized = keyOf(key)
    if (this.current?.key === serialized) return this.current.promise

    this.cancelCurrent('superseded route load')
    const controller = new AbortController()
    const localGeneration = ++this.generation

    const promise = this.loader(key, controller.signal)
      .then(value => {
        if (
          this.disposed ||
          controller.signal.aborted ||
          localGeneration !== this.generation ||
          this.current?.generation !== localGeneration
        ) {
          throw new StaleRouteLoadError()
        }
        return value
      })
      .finally(() => {
        if (this.current?.generation === localGeneration) {
          this.current = undefined
        }
      })

    this.current = {
      key: serialized,
      generation: localGeneration,
      controller,
      promise,
    }
    return promise
  }

  cancelCurrent(reason = 'cancelled'): void {
    if (!this.current) return
    this.current.controller.abort(reason)
    this.current = undefined
    this.generation += 1
  }

  dispose(): void {
    if (this.disposed) return
    this.cancelCurrent('coordinator disposed')
    this.disposed = true
  }
}
```

注意双保险：AbortController 尽力停止 loader；generation 防止第三方 loader 忽略 signal 后仍回写。

相同 key singleflight 只覆盖当前 in-flight，不缓存成功值。成功缓存、TTL、SSR hydration 与 stale-while-revalidate 应由 query cache 负责，避免把 coordinator 变成另一套不完整 Pinia。

### 8. 接入 Router 的取舍

在 `beforeResolve` 接入会阻止 navigation finalize，适合“没有数据就不允许进入”的页面：

```ts
router.beforeResolve(async to => {
  if (to.name !== 'ticket') return true
  const key = parseRouteKey(to)
  if (!key) return { name: 'not-found' }

  try {
    const ticket = await coordinator.load(key)
    const tickets = useTicketStore(pinia)
    // 按 key 写缓存，而不是写一个无身份的 currentTicket。
    tickets.upsert(key, ticket)
    return true
  } catch (error) {
    if (error instanceof StaleRouteLoadError) return false
    return { name: 'ticket-load-error', query: { from: to.fullPath } }
  }
})
```

更常见的产品可能允许先完成导航，再由 route component/query cache 显示 skeleton；这时取消跟随 component scope/route key。两种方案都必须把结果按 key 存储，不能让旧 42 覆盖全局 `currentTicket` 后显示在 43。

Router 自己会在 guard groups 之间检查 `pendingLocation`，但它不知道 coordinator 内部 fetch。两层取消互补。

### 9. 并发 SSR 测试

Deferred helper：

```ts
export interface Deferred<T> {
  promise: Promise<T>
  resolve(value: T): void
  reject(reason: unknown): void
}

export function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}
```

测试骨架：

```ts
it('isolates two interleaved SSR requests', async () => {
  const allowA = deferred<boolean>()
  const allowB = deferred<boolean>()

  const requestA = renderRequest({
    url: '/tenant-a/tickets/42',
    session: {
      user: { id: 'user-a', displayName: 'Alice', tenantId: 'tenant-a' },
      token: 'SECRET-A',
    },
    services: { isTenantAllowed: () => allowA.promise },
  })

  const requestB = renderRequest({
    url: '/tenant-b/tickets/42',
    session: {
      user: { id: 'user-b', displayName: 'Bob', tenantId: 'tenant-b' },
      token: 'SECRET-B',
    },
    services: { isTenantAllowed: () => allowB.promise },
  })

  allowB.resolve(true)
  const b = await requestB
  allowA.resolve(true)
  const a = await requestA

  expect(a.html + a.state).toContain('Alice')
  expect(a.html + a.state).not.toContain('Bob')
  expect(b.html + b.state).toContain('Bob')
  expect(b.html + b.state).not.toContain('Alice')
  expect(a.html + a.state + b.html + b.state).not.toContain('SECRET-')
})
```

要直接证明 identity，可把 `createRequestApp()` 单独调用两次：

```ts
const a = createRequestApp()
const b = createRequestApp()

expect(a.app).not.toBe(b.app)
expect(a.router).not.toBe(b.router)
expect(a.pinia).not.toBe(b.pinia)
expect(useAuthStore(a.pinia)).not.toBe(useAuthStore(b.pinia))
```

固定 seed 的 100 次交错不需要真实并发线程：生成一组 request barriers，按 seed 决定 resolve 顺序，最后检查每份 HTML/state 只含自身 canary。失败日志输出 seed 以便复现。

### 10. 快速导航测试

```ts
it('does not return the old route result after a new key starts', async () => {
  const load42 = deferred<{ id: string }>()
  const load43 = deferred<{ id: string }>()

  const coordinator = new DefaultRouteLoadCoordinator((key, signal) => {
    // 故意让 promise 忽略 abort，以验证 generation 第二道防线。
    return key.ticketId === '42' ? load42.promise : load43.promise
  })

  const p42 = coordinator.load({ tenantId: 'a', ticketId: '42' })
  const p43 = coordinator.load({ tenantId: 'a', ticketId: '43' })

  load43.resolve({ id: '43' })
  await expect(p43).resolves.toEqual({ id: '43' })

  load42.resolve({ id: '42' })
  await expect(p42).rejects.toBeInstanceOf(StaleRouteLoadError)
})
```

还应测试：同 key 两次返回同一个 Promise；loader reject 后下一次可重试；dispose 后拒绝；不同 tenant 的相同 ticket id 不是同 key。

### 11. Router 源码调用链答案

Router 5.3.0：

```text
createRouter(options)
  → createRouterMatcher(options.routes, options)
    → addRoute/normalize record
    → tokenizePath
    → tokensToParser + score

push / replace
  → pushWithRedirect
  → resolve
  → navigate(to, from)
    → leavingRecords / updatingRecords / enteringRecords
    → beforeRouteLeave + leaveGuards
    → checkCanceledNavigationAndReject
    → global beforeEach
    → cancellation check
    → beforeRouteUpdate + updateGuards
    → cancellation check
    → route beforeEnter
    → cancellation check
    → beforeRouteEnter
    → cancellation check
    → global beforeResolve
    → cancellation check
  → finalizeNavigation
    → history push/replace
    → currentRoute.value = to
    → scroll
  → afterEach(to, from, failure)
```

`runGuardQueue` 把 guards 串成 Promise chain；每一阶段加入 cancellation guard，避免旧导航继续确认。`afterEach` 用于观测，返回值不能撤销已经确认的导航。

Matcher 的 tokenizer 负责把 path 拆成静态/参数等 tokens；parser/ranker 负责 parse/stringify/score；matcher 负责记录层级、alias、name map 和 resolve。这比“把 routes 从上到下试一遍正则”更精确。

### 12. Pinia 源码调用链答案

Pinia 4.0.3：

```text
createPinia
  → effectScope
  → state = ref({})
  → plugin queue + store registry
  → install(app): setActivePinia + provide(piniaSymbol)

defineStore(id, options/setup)
  → 返回 useStore(pinia?)
    → 显式 pinia / inject(piniaSymbol) / activePinia
    → registry 是否已有 id
      ├─ options → createOptionsStore → createSetupStore
      └─ setup   → createSetupStore
    → 返回 registry 中 store
```

`createSetupStore` 建 effect scope、state、subscriptions、action wrappers、plugins 与 dispose。`$patch` 暂停普通监听并聚合 mutation subscription，但不是数据库事务。action wrapper 调用 `$onAction` listeners，并为 Promise 安排 after/onError。

`storeToRefs` 遍历 raw store，把 computed/ref/reactive 属性变成 refs，忽略 methods 与非响应属性。

服务端风险来自：没有 injection context 或显式 pinia 时可能回退 `activePinia`。Pinia 4 的 `PINIA_R1004` 诊断直接把它描述为 cross-request pollution 风险。解决方式是请求工厂 + 外部调用显式 `useStore(pinia)`，不是在并发请求间不断 `setActivePinia` 抢一个全局槽位。

### 13. 常见错误

| 错误 | 为什么错 | 修复 |
| --- | --- | --- |
| 模块顶层创建 app/pinia | 所有 SSR 请求共享 registry/state | 每请求工厂 |
| 模块顶层 `useStore()` | 锁住错误 active pinia | setup 内调用或显式传 pinia |
| token 放 Pinia 后整体序列化 | secret 泄漏客户端 | server-only context + state 白名单 |
| guard fetch 后写 `currentTicket` | 旧导航覆盖新路由 | abort+generation+keyed cache |
| 认为 Router cancel 会 abort fetch | Router 不拥有外部请求 | coordinator cleanup |
| 直接解构 store state | 丢失响应连接 | storeToRefs |
| 用 `$patch` 当跨 store 事务 | 无 rollback/并发协议 | 后端事务/显式 saga |
| 串行 SSR 测试 | 看不到 await 交错污染 | barrier 并发测试 |

### 14. 生产边界

这套实现证明进程内、请求级 Vue 状态隔离。它不解决：

- 后端数据库多租户行级权限；
- 分布式 session/cache 一致性；
- 多 region replication；
- 网络重试幂等；
- streaming headers 已发送后的错误恢复；
- CDN HTML 私有缓存隔离。

高级 Vue 工程师不必独自实现所有后端协议，但必须知道 UI/store/router 边界在哪里结束，并把不可承担的保证写进 ADR、接口和测试。
