# 第 06 章答案：状态所有权与并发一致性

> 参考答案不是唯一架构，但每个选择必须能回答“谁拥有、何时过期、失败后是什么、并发时谁赢”。

## 题 1 参考答案：状态地图不是文件目录图

### 1. 状态归属表

| 状态 | owner / 真相源 | 生命周期 | 持久化与失效 | SSR 注意 |
|---|---|---|---|---|
| 当前用户摘要 | session store；真相源 `/me` | 登录会话 | 刷新后重取；logout 清空 | 每请求注入，payload 仅含可公开摘要 |
| 当前租户 ID | session store + URL 可选；服务端校验 | 会话/路由 | 可保存非敏感最近选择；无权限即清 | 不信任客户端 tenantId |
| 权限代码 | session store；真相源授权服务 | 会话 | 不持久化；切租户/角色变化重取 | 只控制 UI，不能替代后端授权 |
| 列表筛选/分页 | Router query | 浏览历史 | URL 自然恢复 | 服务端渲染使用当前 URL |
| hover 行 | 行/表格组件 `ref` | 组件实例 | 不持久化 | 服务端默认无 hover |
| 列宽/列显隐 | preference store + versioned storage | 跨会话 | 白名单、迁移、重置 | SSR 用默认值，注意水合一致性 |
| 工单列表 | query cache；真相源服务端 | stale/cache time | mutation/push/focus 失效 | query client 每请求创建 |
| 工单详情 | query cache；真相源服务端 | stale/cache time | version 较新写入、失效重取 | 禁止跨请求共享 |
| 编辑草稿 | 页面/feature store；用户输入是真相 | 编辑流程 | 可选版本化本地草稿；提交/放弃清理 | 通常不 SSR 序列化 |
| toast 队列 | app UI service/store | 数秒 | 自动消费，不持久化 | 服务端不创建计时器 |
| WebSocket | resource service | 登录且页面活跃 | logout/切租户断开，断线重连 | 服务端不创建浏览器连接 |
| token | HttpOnly/Secure/SameSite Cookie | 会话 | 由服务端/认证流程轮换 | 不进 Pinia/payload/localStorage |
| 是否保存 | mutation 状态或页面状态 | 单次写入 | Promise settled 后结束 | 不从服务端序列化 |
| 逾期数 | query selector/computed | 随列表 | 随源数据重算 | 不重复存储 |

注意：“当前租户 ID”可以同时反映在 URL 和 session store，但必须规定主从。例如 URL 是进入页面的选择意图，session action 经过权限校验后建立有效上下文；不能让二者互相 watcher 无条件回写。

### 2. Session Store

```ts
import { defineStore } from 'pinia'

interface UserSummary {
  id: string
  displayName: string
}

interface EstablishedSession {
  user: UserSummary
  tenantId: string
  permissionCodes: readonly string[]
}

interface SessionState {
  status: 'anonymous' | 'established'
  user: UserSummary | null
  tenantId: string | null
  permissionCodes: string[]
}

export const useSessionStore = defineStore('session', {
  state: (): SessionState => ({
    status: 'anonymous',
    user: null,
    tenantId: null,
    permissionCodes: [],
  }),

  getters: {
    can: state => (code: string) =>
      state.status === 'established' && state.permissionCodes.includes(code),
  },

  actions: {
    establish(input: EstablishedSession) {
      this.$patch({
        status: 'established',
        user: input.user,
        tenantId: input.tenantId,
        permissionCodes: [...new Set(input.permissionCodes)],
      })
    },

    clear() {
      this.$patch({
        status: 'anonymous',
        user: null,
        tenantId: null,
        permissionCodes: [],
      })
    },
  },
})
```

更强的类型建模可把匿名/已登录状态做成 discriminated union，但 Pinia Options Store 对嵌套 union 的直接变更可能不够顺手。无论语法怎样，必须保证不存在 `user === null` 却仍有上一租户权限的中间状态。

### 3. 偏好 envelope 与迁移

```ts
type Theme = 'light' | 'dark' | 'system'

interface PreferenceV2 {
  version: 2
  updatedAt: number
  writerId: string
  data: {
    theme: Theme
    density: 'comfortable' | 'compact'
    visibleColumns: string[]
    widths: Record<string, number>
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isTheme(value: unknown): value is Theme {
  return value === 'light' || value === 'dark' || value === 'system'
}

function strings(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string')
    : []
}

function safeWidths(value: unknown): Record<string, number> {
  if (!isRecord(value)) return {}
  return Object.fromEntries(
    Object.entries(value).filter((entry): entry is [string, number] =>
      typeof entry[1] === 'number' && Number.isFinite(entry[1]) &&
      entry[1] >= 48 && entry[1] <= 1200,
    ),
  )
}

function decodePreference(value: unknown, writerId: string): PreferenceV2 | null {
  if (!isRecord(value) || !isRecord(value.data)) return null

  if (value.version === 1) {
    return {
      version: 2,
      updatedAt: Date.now(),
      writerId,
      data: {
        theme: isTheme(value.data.theme) ? value.data.theme : 'system',
        density: 'comfortable',
        visibleColumns: strings(value.data.columns),
        widths: safeWidths(value.data.widths),
      },
    }
  }

  if (
    value.version !== 2 ||
    typeof value.updatedAt !== 'number' ||
    typeof value.writerId !== 'string' ||
    !isTheme(value.data.theme) ||
    (value.data.density !== 'comfortable' && value.data.density !== 'compact')
  ) return null

  return {
    version: 2,
    updatedAt: value.updatedAt,
    writerId: value.writerId,
    data: {
      theme: value.data.theme,
      density: value.data.density,
      visibleColumns: strings(value.data.visibleColumns),
      widths: safeWidths(value.data.widths),
    },
  }
}

function readPreference(storage: Storage, writerId: string): PreferenceV2 | null {
  try {
    const text = storage.getItem('ops.preference')
    return text === null ? null : decodePreference(JSON.parse(text), writerId)
  } catch {
    return null
  }
}
```

这里选择 `updatedAt` 的 last-write-wins，并用 `writerId` 在时间相同时稳定裁决。真实协作草稿通常不能用这种策略，因为覆盖代价更高，应使用服务端版本或提示冲突。

### 4. 切换租户的事务边界

```text
用户选择 t2
  -> UI 进入 switching，禁止领域写操作
  -> Abort t1 的 query/mutation（不能只隐藏响应）
  -> 断开 t1 WebSocket / 停止订阅
  -> 清除或隔离 t1 的敏感 query cache
  -> 服务端确认用户可访问 t2
  -> session.establish(t2 的权限上下文)
  -> router.replace(默认 t2 URL)
  -> 建立 t2 query client namespace / WebSocket
  -> 预取 t2 首屏
  -> UI ready
失败
  -> 保持无租户安全态或回到明确重新验证过的 t1
```

不要先把 `tenantId` 改成 t2，再让页面沿用 t1 缓存。也不要只靠 UI 隐藏数据；缓存 key 必须包含租户，后端必须重新授权。

### 5. 关键测试

```ts
it('clear 同时清除 user、tenant 和 permissions')
it('损坏 JSON 返回 null 而不是抛出导致应用白屏')
it('v1 偏好迁移为 v2 并补默认 density')
it('并发 SSR 请求各有独立 Pinia state')
it('切租户后旧租户慢响应不能写入新租户缓存')
it('未知持久化版本被忽略')
```

### 6. 常见错误答案

- “都放 Pinia，方便”：没有回答过期、缓存、URL 和资源销毁。
- “权限进 localStorage，启动快”：XSS 可读且权限随时可能变化；后端仍不应信任。
- “SSR 模块单例能省内存”：把不同用户的数据放进同一对象是严重隔离事故。
- “watch 所有 state 然后 JSON.stringify”：扩大泄密面，并把瞬时状态和服务端缓存永久化。

---

## 题 2 参考答案：以同实体写队列建立顺序

这里选择“**同一实体串行，不同实体并行**”。它牺牲同一工单的写吞吐，却让线性化顺序与用户提交顺序一致，回滚也不会跨 mutation 覆盖。适合标题编辑；高频协作文本应使用另一套协议。

### 1. 类型与 key

```ts
interface Ticket {
  id: string
  tenantId: string
  title: string
  status: 'open' | 'closed'
  assigneeId: string | null
  version: number
  pending?: boolean
}

interface TicketQuery {
  tenantId: string
  status?: Ticket['status']
  assigneeId?: string
  page: number
  pageSize: number
}

const keys = {
  root: ['ticket'] as const,
  lists: (tenantId: string) => ['ticket', tenantId, 'list'] as const,
  list: (query: TicketQuery) => ['ticket', query.tenantId, 'list', {
    status: query.status ?? null,
    assigneeId: query.assigneeId ?? null,
    page: query.page,
    pageSize: query.pageSize,
  }] as const,
  detail: (tenantId: string, id: string) =>
    ['ticket', tenantId, 'detail', id] as const,
}
```

### 2. 最小依赖接口

```ts
interface QueryClientLike {
  cancelQueries(options: { queryKey: readonly unknown[] }): Promise<void>
  getQueryData<T>(key: readonly unknown[]): T | undefined
  setQueryData<T>(key: readonly unknown[], value: T | undefined): void
  invalidateQueries(options: { queryKey: readonly unknown[] }): Promise<void>
  removeQueries(options: { queryKey: readonly unknown[] }): void
}

interface Repository {
  updateTitle(
    input: { tenantId: string; id: string; title: string; expectedVersion: number },
    signal: AbortSignal,
  ): Promise<Ticket>
}

class ConflictError extends Error {
  constructor(readonly serverTicket: Ticket) {
    super('Ticket version conflict')
  }
}
```

### 3. 协调器核心实现

```ts
type UpdateInput = {
  tenantId: string
  id: string
  title: string
  expectedVersion: number
}

export function createTicketCoordinator(
  client: QueryClientLike,
  repository: Repository,
) {
  const tails = new Map<string, Promise<void>>()
  const controllers = new Map<string, Set<AbortController>>()

  const entityKey = (tenantId: string, id: string) => `${tenantId}:${id}`

  function track(entity: string, controller: AbortController) {
    const set = controllers.get(entity) ?? new Set<AbortController>()
    set.add(controller)
    controllers.set(entity, set)
    return () => {
      set.delete(controller)
      if (set.size === 0) controllers.delete(entity)
    }
  }

  async function runUpdate(input: UpdateInput): Promise<Ticket> {
    const detailKey = keys.detail(input.tenantId, input.id)
    const listPrefix = keys.lists(input.tenantId)
    const entity = entityKey(input.tenantId, input.id)
    const controller = new AbortController()
    const untrack = track(entity, controller)

    await client.cancelQueries({ queryKey: detailKey })
    const previous = client.getQueryData<Ticket>(detailKey)

    // 队列中的后一个动作不能盲用调用时的 expectedVersion。
    // 若缓存已有更高已确认版本，以它作为比较交换基线。
    const expectedVersion = previous && !previous.pending
      ? previous.version
      : input.expectedVersion

    if (previous) {
      client.setQueryData<Ticket>(detailKey, {
        ...previous,
        title: input.title,
        pending: true,
      })
    }

    try {
      const confirmed = await repository.updateTitle(
        { ...input, expectedVersion },
        controller.signal,
      )

      const current = client.getQueryData<Ticket>(detailKey)
      if (!current || confirmed.version >= current.version || current.pending) {
        client.setQueryData(detailKey, { ...confirmed, pending: false })
      }

      // 标题是否影响任意筛选/排序取决于产品规则。无法证明就有界失效本租户 lists。
      await client.invalidateQueries({ queryKey: listPrefix })
      return confirmed
    } catch (error) {
      // 串行保证此时没有更新的同实体 mutation 已应用，因此本快照可安全回滚。
      client.setQueryData(detailKey, previous)
      throw error
    } finally {
      untrack()
      await client.invalidateQueries({ queryKey: detailKey })
    }
  }

  function updateTitle(input: UpdateInput): Promise<Ticket> {
    const entity = entityKey(input.tenantId, input.id)
    const before = tails.get(entity) ?? Promise.resolve()

    const result = before
      .catch(() => undefined) // 前一任务失败不阻塞后续用户意图
      .then(() => runUpdate(input))

    const tail = result.then(() => undefined, () => undefined)
    tails.set(entity, tail)
    void tail.finally(() => {
      if (tails.get(entity) === tail) tails.delete(entity)
    })
    return result
  }

  function acceptPush(event: {
    tenantId: string
    id: string
    snapshot?: Ticket
  }) {
    const key = keys.detail(event.tenantId, event.id)
    const current = client.getQueryData<Ticket>(key)
    const incoming = event.snapshot

    // 正在编辑时不让推送静默覆盖用户意图；先以失效/冲突提示处理。
    if (incoming && !current?.pending && (!current || incoming.version > current.version)) {
      client.setQueryData(key, incoming)
    }

    void client.invalidateQueries({ queryKey: keys.lists(event.tenantId) })
    if (!incoming || current?.pending) {
      void client.invalidateQueries({ queryKey: key })
    }
  }

  function clearTenant(tenantId: string) {
    for (const [entity, set] of controllers) {
      if (!entity.startsWith(`${tenantId}:`)) continue
      for (const controller of set) controller.abort('tenant switched')
      controllers.delete(entity)
      tails.delete(entity)
    }
    client.removeQueries({ queryKey: ['ticket', tenantId] })
  }

  return { updateTitle, acceptPush, clearTenant }
}
```

### 4. 关键时间线

用户依次提交 B、C：

```text
t0 cache=A(v1)
t1 enqueue B
t2 B optimistic -> B(v1,pending)
t3 enqueue C（尚未执行）
t4 server confirms B(v2) -> cache B(v2)
t5 C starts，读取最新 v2 -> optimistic C(v2,pending)
t6 server confirms C(v3) -> cache C(v3)
```

没有“C 先成功、B 后回来”的可能，因为同实体串行。不同工单仍可并发。

若 B 失败：回滚 A(v1)，C 随后仍会执行。产品也可以选择“前一保存失败就暂停队列并让用户处理”，那是另一种合理失败语义，但要明确。

### 5. 测试骨架

```ts
import { describe, expect, it, vi } from 'vitest'

it('同实体按提交顺序调用 repository', async () => {
  const first = deferred<Ticket>()
  const second = deferred<Ticket>()
  const update = vi.fn()
    .mockReturnValueOnce(first.promise)
    .mockReturnValueOnce(second.promise)

  const coordinator = createTicketCoordinator(fakeClient(ticketV1), { updateTitle: update })
  const pB = coordinator.updateTitle({ tenantId: 't1', id: '1', title: 'B', expectedVersion: 1 })
  const pC = coordinator.updateTitle({ tenantId: 't1', id: '1', title: 'C', expectedVersion: 1 })

  expect(update).toHaveBeenCalledTimes(1)
  first.resolve({ ...ticketV1, title: 'B', version: 2 })
  await pB
  await Promise.resolve()
  expect(update).toHaveBeenCalledTimes(2)
  second.resolve({ ...ticketV1, title: 'C', version: 3 })

  await expect(pC).resolves.toMatchObject({ title: 'C', version: 3 })
})

it('网络失败恢复最后确认的快照', async () => {
  const client = fakeClient(ticketV1)
  const coordinator = createTicketCoordinator(client, rejectingRepository(new TypeError('offline')))

  await expect(coordinator.updateTitle({
    tenantId: 't1', id: '1', title: 'B', expectedVersion: 1,
  })).rejects.toThrow('offline')

  expect(client.getQueryData(keys.detail('t1', '1'))).toEqual(ticketV1)
})

it('低版本 push 不覆盖高版本缓存', () => {
  const client = fakeClient({ ...ticketV1, title: 'C', version: 3 })
  const coordinator = createTicketCoordinator(client, unusedRepository())

  coordinator.acceptPush({
    tenantId: 't1', id: '1', snapshot: { ...ticketV1, title: 'B', version: 2 },
  })

  expect(client.getQueryData<Ticket>(keys.detail('t1', '1'))?.title).toBe('C')
})

it('切租户 abort 在途请求并移除该租户缓存')
it('409 暴露 serverTicket，不做无限重试')
it('不同租户相同 id 使用不同 key')
```

真实 TanStack Query 实现可以把快照/回滚放在 mutation lifecycle 中；这里显式写出协调器，是为了看清协议而不是鼓励重复造轮子。

### 6. 列表为何只做有界失效

标题更新看似只改一个字段，但列表可能按标题搜索、按更新时间排序，实体还可能从本页移到下一页。除非产品规则能证明：

- 当前 list 一定包含该 id；
- 更新不影响筛选命中；
- 更新不影响排序和分页位置；
- 服务端响应含列表需要的全部字段；

否则只精确写 detail，并让 `['ticket', tenantId, 'list']` stale 是更可靠的折中。不是“刷新全应用”。

### 7. 生产限制与进一步方案

- 串行队列不适合多人实时文档；那需要 OT/CRDT 或服务端合并协议。
- 页面刷新会丢内存队列；离线可靠写入需要持久 outbox、幂等键和重放协议。
- Abort 只表示客户端不再等待，不保证服务端没有完成写入；幂等键和服务端版本仍然必要。
- `409/412` 应保留用户输入，展示 `base/local/server` 三方差异，而不是直接回滚后丢稿。
- 推送断线后必须 HTTP 重取；version 只能拒绝旧消息，不能发现所有漏消息。

### 8. 错误方案

```ts
// ❌ 两个并发请求共享一个 previous，任意失败都能覆盖后来的成功
const previous = cache.ticket
cache.ticket.title = next
api.update(next).catch(() => { cache.ticket = previous })
```

```ts
// ❌ 只比较响应到达顺序，没有服务端版本或客户端 sequence
api.update(next).then(ticket => { cache.ticket = ticket })
```

```ts
// ❌ 更新一条工单后让全站查询全部失效
queryClient.invalidateQueries()
```

支付、权限修改、库存扣减不应照搬乐观标题更新：它们的失败成本高、服务端校验复杂，UI 先假装成功会造成错误承诺。此时优先 pessimistic 状态机：`idle -> submitting -> confirmed | failed`。

### 复建要求

合上答案后，重新画出两张图：

1. 五类状态到 owner 的映射；
2. 乐观写入从取消读取、快照、提交、确认/回滚到重验证的时间线。

如果画不出，说明你记住了 API，却还没有掌握一致性模型。
