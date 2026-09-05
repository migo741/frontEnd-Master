# 第 07 章答案：把导航当成可取消事务

## 题 1 参考答案：Abort 节流，generation 保正确

### 1. 状态类型

```ts
export type ResourceState<T> =
  | { status: 'idle'; data: null; error: null }
  | { status: 'loading'; data: T | null; error: null; showingPrevious: boolean }
  | { status: 'success'; data: T; error: null }
  | { status: 'error'; data: T | null; error: unknown }
```

使用 union 而不是四个互相独立的布尔值，可排除 `loading=true && error!=null && data=null` 等无定义组合。`showingPrevious` 告诉模板当前数据只是过渡展示，不能把 A 的内容冒充成 B 的新结果。

### 2. 可运行核心实现

```ts
import {
  onScopeDispose,
  readonly,
  shallowRef,
  watch,
  type Ref,
} from 'vue'

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

export function useRouteResource<K, T>(options: {
  key: Readonly<Ref<K | null>>
  load: (key: K, signal: AbortSignal) => Promise<T>
}) {
  const state = shallowRef<ResourceState<T>>({
    status: 'idle', data: null, error: null,
  })

  let generation = 0
  let controller: AbortController | null = null
  let disposed = false

  async function execute(key: K): Promise<void> {
    const mine = ++generation
    controller?.abort('superseded')
    const currentController = new AbortController()
    controller = currentController

    const previous = state.value.data
    state.value = {
      status: 'loading',
      data: previous,
      error: null,
      showingPrevious: previous !== null,
    }

    try {
      const data = await options.load(key, currentController.signal)
      if (disposed || mine !== generation) return
      state.value = { status: 'success', data, error: null }
    } catch (error) {
      if (disposed || mine !== generation || isAbortError(error)) return
      state.value = { status: 'error', data: previous, error }
    } finally {
      if (mine === generation) controller = null
    }
  }

  const stop = watch(
    options.key,
    (key) => {
      if (key === null) {
        ++generation
        controller?.abort('invalid key')
        controller = null
        state.value = { status: 'idle', data: null, error: null }
        return
      }
      void execute(key)
    },
    { immediate: true },
  )

  async function reload(): Promise<void> {
    const key = options.key.value
    if (key !== null) await execute(key)
  }

  onScopeDispose(() => {
    disposed = true
    ++generation
    stop()
    controller?.abort('scope disposed')
    controller = null
  })

  return { state: readonly(state), reload }
}
```

这里的线性化点是 `mine === generation` 的提交检查。`reload` 也走同一个 `execute`，因此会提升 generation 并取消前一任务，不会开第二条无协调路径。`Readonly` 使用 TypeScript 内置工具类型；`Ref` 来自 Vue。

### 3. 路由输入解析

```ts
type TenantId = string & { readonly __brand: 'TenantId' }
type TicketId = string & { readonly __brand: 'TicketId' }

function one(value: unknown): string | null {
  if (typeof value === 'string') return value
  if (Array.isArray(value) && typeof value[0] === 'string') return value[0]
  return null
}

function parseTenantId(value: unknown): TenantId | null {
  const text = one(value)
  return text && /^tn_[a-z0-9]{8,32}$/i.test(text) ? text as TenantId : null
}

function parseTicketId(value: unknown): TicketId | null {
  const text = one(value)
  return text && /^TK-[0-9]{1,12}$/.test(text) ? text as TicketId : null
}

interface TicketKey {
  tenantId: TenantId
  ticketId: TicketId
}

const resourceKey = computed<TicketKey | null>(() => {
  const tenantId = parseTenantId(route.params.tenantId)
  const ticketId = parseTicketId(route.params.ticketId)
  return tenantId && ticketId ? { tenantId, ticketId } : null
})
```

这里 `as TenantId` 位于完成正则验证的构造边界，不是对任意路由值断言。更成熟项目可用 schema 的 transform/brand。

类型化导航：

```ts
await router.push({
  name: 'ticket-detail',
  params: { tenantId: tenant.id, ticketId: ticket.id },
})
```

Typed route 会校验必需 params 和 route name，但地址栏仍需上面的运行时解析。

### 4. 模板穷尽展示

```vue
<template>
  <EmptyRouteState v-if="state.status === 'idle'" />

  <template v-else-if="state.status === 'loading'">
    <TicketView v-if="state.data" :ticket="state.data" inert aria-busy="true" />
    <TicketSkeleton v-else />
    <span class="sr-only">正在加载新的工单</span>
  </template>

  <TicketView v-else-if="state.status === 'success'" :ticket="state.data" />

  <ErrorState
    v-else
    :error="state.error"
    :previous-data="state.data"
    @retry="reload"
  />
</template>
```

真实产品若在切换租户时保留前一租户数据，哪怕标 stale 也有窥视风险。此时 key 跨租户变化应立即清空 previous；可给 composable 加 `canRetainPrevious(oldKey, newKey)`，默认 false。

### 5. 乱序测试

```ts
import { effectScope, ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((ok, fail) => {
    resolve = ok
    reject = fail
  })
  return { promise, resolve, reject }
}

it('A 晚到不能覆盖 B', async () => {
  const key = ref<string | null>('A')
  const a = deferred<string>()
  const b = deferred<string>()
  const load = vi.fn((value: string) => value === 'A' ? a.promise : b.promise)

  const scope = effectScope()
  const resource = scope.run(() => useRouteResource({ key, load }))!

  key.value = 'B'
  await Promise.resolve()
  b.resolve('data-B')
  await Promise.resolve()
  expect(resource.state.value).toMatchObject({ status: 'success', data: 'data-B' })

  a.resolve('data-A') // 模拟忽略 Abort 的旧 Promise
  await Promise.resolve()
  expect(resource.state.value).toMatchObject({ status: 'success', data: 'data-B' })
  scope.stop()
})

it('dispose 后不提交', async () => {
  const key = ref<string | null>('A')
  const request = deferred<string>()
  const scope = effectScope()
  const resource = scope.run(() => useRouteResource({
    key,
    load: () => request.promise,
  }))!

  scope.stop()
  request.resolve('late')
  await Promise.resolve()

  expect(resource.state.value.status).not.toBe('success')
})

it('key 变 null 后旧结果被忽略')
it('真实错误进入 error 且 reload 可以恢复')
it('AbortError 不向用户显示')
```

### 6. 何时用导航前加载

如果实体是否存在/能否访问决定是否允许进入，使用 `beforeResolve` 预取关键实体更合适；若页面能自然显示骨架且尽快更新 URL 更重要，则在页面内加载。无论在哪加载，都最好复用同一个 query cache/repository，避免守卫和页面各请求一次。

### 7. 错误方案

- 只用 Abort：无法阻止不支持取消的 Promise 提交。
- 只在 `onMounted` 加载：参数变化复用实例时不执行。
- `RouterView :key=fullPath`：用全量销毁掩盖竞态，丢失页面状态并扩大成本。
- catch 所有错误都忽略：真实网络/权限错误变成永久 loading。

---

## 题 2 参考答案：会话恢复是导航前置依赖

### 1. 路由契约

```ts
declare module 'vue-router' {
  interface RouteMeta {
    title: string
    requiresAuth: boolean
    permission?: PermissionCode
    criticalEntity?: 'ticket'
    keepAlive?: boolean
  }
}

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/pages/LoginPage.vue'),
    meta: { title: '登录', requiresAuth: false },
  },
  {
    path: '/admin/tickets',
    name: 'ticket-admin',
    component: () => import('@/pages/TicketAdminPage.vue'),
    meta: {
      title: '工单管理',
      requiresAuth: true,
      permission: 'ticket:admin',
      keepAlive: true,
    },
  },
]
```

### 2. `/me` singleflight 状态机

```ts
type SessionState =
  | { status: 'unknown'; user: null; permissions: readonly string[] }
  | { status: 'restoring'; user: null; permissions: readonly string[] }
  | { status: 'authenticated'; user: User; permissions: readonly PermissionCode[] }
  | { status: 'anonymous'; user: null; permissions: readonly string[] }
  | { status: 'error'; user: null; permissions: readonly string[]; error: unknown }

let restoreInFlight: Promise<void> | null = null

async function ensureSession(): Promise<void> {
  if (session.state.status === 'authenticated' || session.state.status === 'anonymous') return
  if (restoreInFlight) return restoreInFlight

  restoreInFlight = (async () => {
    session.beginRestore()
    try {
      const me = await authRepository.me()
      session.establish(me)
    } catch (error) {
      if (isUnauthorized(error)) session.becomeAnonymous()
      else {
        session.failRestore(error)
        throw error
      }
    } finally {
      restoreInFlight = null
    }
  })()

  return restoreInFlight
}
```

网络错误不等于匿名。若把所有失败都当 401，断网用户会被踢回登录页，并可能丢失工作。

### 3. 守卫分工

```ts
router.beforeEach(async (to) => {
  if (to.meta.requiresAuth || to.name === 'login') {
    try {
      await ensureSession()
    } catch {
      return to.name === 'session-error'
        ? true
        : { name: 'session-error', replace: true }
    }
  }

  if (!to.meta.requiresAuth) {
    if (to.name === 'login' && session.state.status === 'authenticated') {
      return { name: 'home', replace: true }
    }
    return true
  }

  if (session.state.status !== 'authenticated') {
    return {
      name: 'login',
      query: { redirect: safeInternalPath(to.fullPath) },
      replace: true,
    }
  }

  if (to.meta.permission && !session.can(to.meta.permission)) {
    return to.name === 'forbidden' ? true : { name: 'forbidden', replace: true }
  }

  return true
})

router.beforeResolve(async (to) => {
  if (to.meta.criticalEntity !== 'ticket') return true
  const ids = parseTicketRoute(to)
  if (!ids) return { name: 'not-found', replace: true }

  try {
    await ticketQueries.ensureDetail(ids)
    return true
  } catch (error) {
    if (isNotFound(error)) return { name: 'not-found', replace: true }
    if (isForbidden(error)) return { name: 'forbidden', replace: true }
    throw error
  }
})

router.afterEach((to, from, failure) => {
  if (failure) {
    navigationTelemetry.failure({
      from: String(from.name),
      to: String(to.name),
      type: classifyNavigationFailure(failure),
    })
    return
  }

  document.title = `${to.meta.title} · OpsBoard`
  navigationTelemetry.success({ routeName: String(to.name) })
})
```

`beforeEach` 解决身份和通用能力；`beforeResolve` 只加载进入页面所必需的关键实体；`afterEach` 只做不能影响结果的副作用。

### 4. 安全 redirect

```ts
function safeInternalPath(value: unknown): string {
  const raw = Array.isArray(value) ? value[0] : value
  if (typeof raw !== 'string') return '/'
  if (!raw.startsWith('/') || raw.startsWith('//')) return '/'

  try {
    const url = new URL(raw, window.location.origin)
    if (url.origin !== window.location.origin) return '/'
    if (url.pathname === '/login') return '/'
    return `${url.pathname}${url.search}${url.hash}`
  } catch {
    return '/'
  }
}
```

登录后用 `router.replace(safeInternalPath(route.query.redirect))`。更严格的系统可只允许 route name + 受验证 params。

### 5. 决策表

| 情况 | 导航结果 | 数据动作 |
|---|---|---|
| 会话 unknown | 停在 app shell，await singleflight | 仅 `/me` |
| `/me` 401 | login + safe redirect | 清 session/query/连接 |
| `/me` 网络错误 | session-error | 保留本地草稿，不当 logout |
| 权限不足 | 403 replace | 不加载敏感实体 |
| 实体不存在 | 404 replace | detail 负缓存可短时保留 |
| 切租户 | 经 session action 建上下文 | abort/隔离旧租户缓存 |
| 权限在停留时撤销 | 收到 403/push 后刷新 session | 禁用动作、移出页面、保留可导出草稿 |

### 6. 脏表单守卫

```ts
let leaveDecision: Promise<boolean> | null = null

onBeforeRouteLeave(async () => {
  if (!draft.dirty) return true
  if (!leaveDecision) {
    leaveDecision = confirmDiscard().finally(() => { leaveDecision = null })
  }
  return leaveDecision
})
```

singleflight dialog 防止用户连续点击产生多个确认框。若选择“保存并离开”，只有保存成功才返回 true；冲突或网络失败必须留在页面。

### 7. Scroll 与 KeepAlive

```ts
scrollBehavior(to, from, savedPosition) {
  if (savedPosition) return savedPosition
  if (to.hash) return { el: to.hash, top: 64 }
  return { top: 0 }
}
```

KeepAlive 只缓存名单中的列表页，`:max="6"`；key 用稳定 route name + 业务 workspace，而不是任意 fullPath。筛选在 URL/query cache 中恢复，不为每个 query 创建组件实例。页面在 `onActivated` 根据 stale 策略重验证，在 `onDeactivated` 暂停高频订阅。

### 8. Chunk 错误恢复

```ts
router.onError((error, to) => {
  reportError(error, { phase: 'route-load', routeName: to?.name })

  if (!looksLikeChunkLoadError(error)) return
  const buildKey = `chunk-reload:${BUILD_ID}`
  if (sessionStorage.getItem(buildKey)) {
    showFatalUpdateError()
    return
  }
  sessionStorage.setItem(buildKey, '1')
  window.location.reload()
})
```

刷新必须限定 build 和次数，不能对业务异常无限 reload。

### 9. 端到端场景

1. 未登录深链管理页：从未出现管理 DOM，最终到 login 且 redirect 可恢复；
2. 4 个并发导航只调用一次 `/me`；
3. 外部 `redirect=https://evil.example` 登录后回 `/`；
4. 无权限用户不发管理数据请求并到 403；
5. A 导航被 B 取代，只记录 B 成功 PV；
6. 脏表单选择 stay，route 和 URL 保持；
7. 保存失败后不离开；
8. 浏览器后退恢复列表 URL 和滚动；
9. 同一 build chunk 失败最多 reload 一次；
10. 多标签 logout 后另一标签下一请求收 401，清缓存并收敛到登录态。

### 10. 后端不可省略的安全规则

- 从可信 session/token 得到用户身份，不信任客户端传角色；
- 每次请求校验用户、租户、资源和动作；
- 防止只按 `ticketId` 查询导致跨租户 IDOR；
- 权限变化及时生效，关键操作重新鉴权；
- 审计允许/拒绝的敏感动作；
- 只返回当前用户允许看到的字段。

前端隐藏按钮、route meta、动态路由都只是 UX，不是这些规则的替代品。

### 11. 常见错误答案

- `if (!role) router.push('/login')` 写在组件 mount：已经渲染和发请求。
- 把 `/me` 网络失败当 401：断网即退出，语义错误。
- `redirect` 原样赋给 `location.href`：开放重定向。
- `afterEach` 无条件记 PV：取消/失败污染分析。
- `KeepAlive :key="route.fullPath"`：筛选组合无限制造实例。
- 依赖前端 permission 拦接口：攻击者绕过 UI 即可请求。

### 复建要求

关掉答案，画出：

```text
unknown session -> restore -> authenticated/anonymous/error
navigation -> beforeEach -> async component -> beforeResolve -> confirm -> afterEach
```

并在每一条失败边标出：URL、页面、缓存、埋点分别应该是什么状态。
