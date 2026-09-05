# 第 20 章练习：跨缓存、Portal、导航与请求边界

> 本章恰好两题。第一题审计 Vue 内置组件的生命周期；第二题审计 Router + Pinia 的导航竞态与 SSR 隔离。答案不能只贴 demo，必须包含源码调用链、可控异步测试和生产边界。

## 练习 1：可缓存工单页与异步 Overlay 工作台

### 场景

实现一个简化客服工作台：

- 三个工单详情 `A/B/C` 使用同一个 `TicketPage` 组件；
- 页面由 `<KeepAlive :max="2">` 缓存；
- 每页有未提交草稿和每 5 秒一次的状态轮询；
- 点击“审计记录”后异步加载 `AuditPanel`；
- loading content 可在 Suspense boundary 中展示，但错误必须有独立 UI；
- 审计面板放在具备完整对话框行为的 Modal 中，并 Teleport 到 `#overlays`；
- 切页、关闭、快速重开、loader 失败和缓存淘汰都必须正确清理。

### 推荐结构

```vue
<KeepAlive :max="2">
  <TicketPage :key="activeTicketId" :ticket-id="activeTicketId" />
</KeepAlive>

<Teleport to="#overlays">
  <ModalDialog v-if="auditOpen" @close="closeAudit">
    <ErrorBoundary>
      <Suspense>
        <AuditPanel :ticket-id="activeTicketId" />
        <template #fallback><AuditSkeleton /></template>
      </Suspense>
    </ErrorBoundary>
  </ModalDialog>
</Teleport>
```

可调整结构，但必须解释为什么。不要把 `Suspense` 当 error boundary；若你选择不用 Suspense，仍需完成 async loading/error/cancel 测试并写 ADR。

### 任务 A：KeepAlive 所有权

设计 `useTicketPolling(ticketId)`：

- 首次 active 时开始；
- deactivated 后停止或暂停，不在后台继续请求；
- activated 后恢复，不能重复创建两条 interval；
- unmounted/cache eviction 后彻底释放 timer、AbortController、observer；
- 轮询响应带 generation，旧响应不能覆盖新 active ticket；
- 测试使用 fake clock 与 deferred Promise，不真实等待 5 秒。

手算并测试 `max=2` 的序列：

```text
A → B → A → C → B
```

提交每一步 cache 新鲜度、activate/deactivate/unmount 事件和最终仍存活实例。

### 任务 B：Teleport Dialog

Modal 必须满足：

- `role="dialog"`、`aria-modal="true"`、可关联 title；
- 打开后初始焦点合理；
- Tab/Shift+Tab 不逃出 topmost dialog；
- Escape 与 backdrop close reason 可区分；
- 关闭后恢复触发按钮焦点；
- body scroll lock 引用计数正确，嵌套 overlay 不提前解锁；
- target 缺失时有明确失败或 fallback 策略；
- `prefers-reduced-motion` 下不依赖动画完成 cleanup。

测试必须查询真实 `document.querySelector('#overlays')`，不能只查 wrapper 根节点。

### 任务 C：Async/Suspense 状态机

至少覆盖：

- loader resolve；
- loader reject；
- timeout；
- 一次可重试错误，重试成功；
- 快速关闭时旧 loader 完成但不重新打开 UI；
- ticket A panel pending 时切到 B，A 结果不得显示为 B；
- Suspense fallback 不承担 error UI；
- 不支持/不采用 Suspense 时功能仍可用。

定义显式状态，不允许只有三个互相矛盾的 boolean：

```ts
type AsyncPanelState<T> =
  | { tag: 'idle' }
  | { tag: 'pending'; requestId: string }
  | { tag: 'ready'; requestId: string; value: T }
  | { tag: 'failed'; requestId: string; error: Error }
```

### 任务 D：源码审计

报告中固定到 Vue Core `v3.5.42`，解释：

- KeepAlive `cache`、`keys`、`pendingCacheKey`、activate/deactivate；
- max 淘汰为何近似 LRU；
- Teleport 的 main anchors 与 target anchors；
- `defineAsyncComponent` 的 pendingRequest/retry/timeout；
- Suspense activeBranch/pendingBranch/deps/effects；
- 哪些是 public contract，哪些只是当前实现。

### 发散问题

1. 如果页面状态可以由 URL + query cache 恢复，还需要 KeepAlive 吗？
2. 移动端内存紧张时，如何用 RUM 决定 max？
3. 多个微前端都 Teleport 到 body，谁管理 z-index、focus 与 scroll lock？
4. 部署后旧 chunk URL 404，应自动 reload、retry 还是提示用户？风险是什么？

### 交付物

- 可运行 fixture；
- fake-clock/deferred tests；
- 生命周期时间线与 cache 手算表；
- a11y 自动检查 + 键盘路径；
- 一页 ADR：为何使用或不使用 Suspense/KeepAlive。

---

## 练习 2：Router + Pinia 并发导航与 SSR 隔离证明

### 场景

一个 SSR 工单系统有以下线上风险：

- `/tenant-a/tickets/42` 与 `/tenant-b/tickets/42` 可能并发渲染；
- auth/tenant store 曾在模块顶层创建；
- route guard 会异步刷新 session；
- 用户连续点击工单 42、43，42 的慢响应最后覆盖 43；
- 测试只串行请求，从未发现跨请求污染。

### 任务 A：每请求应用工厂

实现：

```ts
export interface RequestApp {
  app: ReturnType<typeof createSSRApp>
  router: Router
  pinia: Pinia
}

export function createRequestApp(): RequestApp

export async function renderRequest(input: {
  url: string
  session: Session
  loadTicket: TicketLoader
}): Promise<{ html: string; state: string }>
```

要求：

- 每次调用创建新 app、memory-history router、pinia；
- `installGuards(router, pinia, services)` 显式接收依赖；
- store 不在模块顶层实例化；
- `router.push(url)` 后等待 ready；
- Pinia hydration payload 安全序列化，绝不包含 token；
- 渲染完成后请求级资源可以释放；
- 未识别 tenant/ticket param 进入确定错误路由。

### 任务 B：导航 loader 协调器

实现可测试协调器：

```ts
export interface RouteLoadKey {
  tenantId: string
  ticketId: string
}

export interface RouteLoadCoordinator<T> {
  load(key: RouteLoadKey): Promise<T>
  cancelCurrent(reason?: string): void
  dispose(): void
}
```

必须具备：

- AbortController；
- generation/version，防止不服从 abort 的 loader 回写；
- 相同 key singleflight 或清楚说明不做的理由；
- 不同 key 启动时取消旧工作；
- navigation failure 与 data failure 分开表达；
- dispose 后拒绝新 load；
- 错误不默认永久缓存。

把协调器接入 `beforeResolve` 或 route component data boundary，并解释选择。不能假设 Router cancellation 自动取消 fetch。

### 任务 C：并发隔离测试

使用 barrier/deferred Promise 同时推进两个 SSR 请求：

```text
request A 设置 tenant/user A
  → 暂停
request B 设置 tenant/user B
  → render B
  → 恢复并 render A
```

断言：

- A HTML/state 只含 A；B 只含 B；
- 两个 pinia、router、store 对象 identity 不同；
- 不包含另一请求的 token/name/ticket；
- 任一请求失败不污染另一个；
- 连续跑 100 个固定 seed 交错调度仍隔离；
- 测试结束无未处理 Promise/active timer。

### 任务 D：Router 源码调用链

以 Router 5.3.0 固定链接说明：

1. `createRouter` 怎样创建 matcher；
2. path tokenizer/parser/ranker 的职责；
3. `navigate` 如何分 leaving/updating/entering records；
4. guard groups 的顺序；
5. cancellation check 为什么要夹在 groups 之间；
6. `finalizeNavigation` 才何时改变 currentRoute/history；
7. afterEach 接收 failure 但不能改变已确认结果。

### 任务 E：Pinia 源码调用链

以 Pinia 4.0.3 固定链接说明：

1. `createPinia` 的 effect scope、root state、store registry；
2. `defineStore` 为什么返回 `useStore` 而非立即创建 store；
3. injection context / explicit pinia / activePinia 的解析；
4. options store 如何进入 setup store 主路径；
5. `$patch`、action wrapper、`storeToRefs`；
6. 为什么全局 activePinia 在服务端会有跨请求风险。

### 发散问题

1. streaming SSR 开始输出后才发现 auth 失败，架构应怎样改变？
2. 多 region 部署时，Pinia 隔离解决不了哪些后端 session 一致性问题？
3. 同一 ticket 的 client cache 如何与 SSR payload 去重？
4. 如果 guard 只为 UX，真正授权应在哪一层执行？

### 交付物

- strict TypeScript request factory；
- route loader coordinator；
- 并发 SSR 与快速导航测试；
- 安全序列化检查；
- Router/Pinia 两张调用链图；
- 一份事故复盘与升级回归清单。
