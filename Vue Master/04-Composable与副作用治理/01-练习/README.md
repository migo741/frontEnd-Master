# 第 04 章练习：可重绑定资源与共享请求所有权

## 练习 1：实现可重绑定、可停止的 `useEventListener`（机制题）

### 契约

```ts
import type { MaybeRefOrGetter } from 'vue'

export interface EventListenerHandle {
  stop(): void
}

export declare function useEventListener<E extends Event>(
  target: MaybeRefOrGetter<EventTarget | null | undefined>,
  type: string,
  listener: (event: E) => void,
  options?: MaybeRefOrGetter<boolean | AddEventListenerOptions | undefined>,
): EventListenerHandle
```

### 语义

1. plain、ref、getter target 均支持；target 从 A→B 时，先从 A 移除，再向 B 添加。
2. options 变化也重新绑定；移除时 capture 语义必须与添加时一致。
3. null target 和 SSR 环境静默不绑定；不得在模块初始化访问 `window`。
4. scope dispose 自动停止；manual `stop()` 永久停止、幂等，之后 target 再变也不能重绑。
5. 同一 target/options 的无关响应式变化不得重复 add。
6. listener throw 不由 composable 吞掉；这是调用方错误边界。
7. 同一个 handle 任意时刻最多拥有一个实际 listener。

### 限制与验收

- 不要求为 `WindowEventMap` 做所有 overload；本题关注所有权。
- 用自建 SpyEventTarget 记录 add/remove 的 target/type/listener/capture。
- 测试 A→B、options capture 变化、null、scope stop、manual stop twice、stop 后输入变化、listener 身份对称。
- 禁止真实浏览器和 sleep；TypeScript strict、禁止 `any`。

### 发散

- 若 target 是 DOM template ref，首次为何为 null？watch 的 `flush` 应选什么？
- 如果希望 KeepAlive deactivated 暂停、activated 恢复，公共状态机要增加什么？

---

## 练习 2：实现按 key singleflight 的请求资源客户端（生产题）

### 场景

同一页面的标题、侧栏和正文会同时加载同一个项目。当前实现发送三次请求。你要创建一个**显式实例化**的 client：相同 key 的进行中读取共享一次 loader；结果 TTL 缓存；消费者离开只取消自己的订阅，最后一个消费者离开才 abort 进行中请求。SSR 每个请求创建独立 client。

### 契约

```ts
import type { DeepReadonly, MaybeRefOrGetter, Ref } from 'vue'

export type ResourceState<T> =
  | { status: 'idle' }
  | { status: 'loading'; previous: T | null }
  | { status: 'success'; data: T; updatedAt: number }
  | { status: 'error'; error: Error; previous: T | null }

export interface ResourceHandle<T> {
  state: DeepReadonly<Ref<ResourceState<T>>>
  refresh(): void
}

export interface ResourceClient<T> {
  useResource(key: MaybeRefOrGetter<string | null>): ResourceHandle<T>
  invalidate(key: string): void
  dispose(): void
}

export declare function createResourceClient<T>(options: {
  loader(key: string, signal: AbortSignal): Promise<T>
  ttlMs: number
  now?: () => number
}): ResourceClient<T>
```

### 精确语义

1. key 要 `trim()`；空/null 为 idle，不请求。
2. 未过期缓存立即 success；过期或 refresh 进入 loading，并保留 previous。
3. 同 client、同规范 key、同时进行中的 load 只调用一次 loader；所有订阅者收到同一结果。
4. 每个 handle/scope 算一个 subscriber。一个离开不得 abort；subscriber 归零时 abort in-flight。
5. invalidate 删除缓存并让当前该 key 订阅者重新加载；旧 generation 后返回不得写缓存/状态。
6. refresh 强制新一代：使当前 key 的旧 in-flight 失效并 abort，然后所有订阅者共享新请求。
7. Abort/失效结果不进入 error；当前有效请求失败进入所有当前订阅者 error，错误不缓存。
8. `dispose()` 幂等：abort 全部、停止内部 scopes、清 map；之后调用任何方法抛 `DisposedClientError`。
9. `ttlMs >= 0`，否则构造时抛错；loader 可能同步 throw 或忽略 signal。

### 规模、测试与交付

- 单 client 最多 1,000 key、同 key 100 subscribers；Map 操作近似 O(1)。
- 实现、所有权图、Vitest：三订阅一次 loader、逐个离开、最后 abort、TTL、乱序 invalidate/refresh、错误广播、dispose、两个 client 不共享。
- 使用 `effectScope` 和 deferred Promise，不真实 sleep；`now` 注入假时钟。
- 发散：若缓存 key 忘记 tenantId，会产生什么安全事故？错误是否应短暂缓存以防故障风暴？
