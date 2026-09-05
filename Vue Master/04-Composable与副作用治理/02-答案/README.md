# 第 04 章答案：可重绑定资源与共享请求所有权

## 练习 1 参考答案：`useEventListener`

### 1. 所有权模型

```text
handle
  ├─ watcher：观察 target/options
  └─ currentBinding：最多一个
       ├─ acquire = target.addEventListener(...)
       └─ release = 同 target/type/wrappedListener/capture remove

manual stop / scope dispose
  └─ stop watcher + release currentBinding（幂等）
```

不能简单在 `watchEffect` 每次执行时 add，然后等下一轮 cleanup remove；如果 getter 因无关依赖重跑但绑定配置未变，会产生无意义解绑/重绑。这里对归一化配置做相等比较。

### 2. 实现

```ts
// useEventListener.ts
import {
  getCurrentScope,
  onScopeDispose,
  toValue,
  watch,
  type MaybeRefOrGetter,
} from 'vue'

export interface EventListenerHandle {
  stop(): void
}

interface BindingConfig {
  target: EventTarget | null
  capture: boolean
  passive: boolean
  once: boolean
  signal: AbortSignal | undefined
}

function normalizeOptions(
  options: boolean | AddEventListenerOptions | undefined,
): Omit<BindingConfig, 'target'> {
  if (typeof options === 'boolean') {
    return {
      capture: options,
      passive: false,
      once: false,
      signal: undefined,
    }
  }
  return {
    capture: Boolean(options?.capture),
    passive: Boolean(options?.passive),
    once: Boolean(options?.once),
    signal: options?.signal,
  }
}

function sameBinding(a: BindingConfig | null, b: BindingConfig): boolean {
  return a?.target === b.target
    && a.capture === b.capture
    && a.passive === b.passive
    && a.once === b.once
    && a.signal === b.signal
}

export function useEventListener<E extends Event>(
  target: MaybeRefOrGetter<EventTarget | null | undefined>,
  type: string,
  listener: (event: E) => void,
  options: MaybeRefOrGetter<boolean | AddEventListenerOptions | undefined> = undefined,
): EventListenerHandle {
  let stopped = false
  let current: BindingConfig | null = null

  // EventTarget 的宽类型只认识 EventListener；转换集中在稳定 wrapper 内。
  const wrapped: EventListener = event => listener(event as E)

  function release(): void {
    if (!current?.target) {
      current = null
      return
    }
    current.target.removeEventListener(type, wrapped, current.capture)
    current = null
  }

  const stopWatch = watch(
    () => {
      const targetValue = toValue(target) ?? null
      const normalized = normalizeOptions(toValue(options))
      return { target: targetValue, ...normalized } satisfies BindingConfig
    },
    next => {
      if (stopped || sameBinding(current, next)) return
      release()
      current = next
      if (!next.target) return
      next.target.addEventListener(type, wrapped, {
        capture: next.capture,
        passive: next.passive,
        once: next.once,
        signal: next.signal,
      })
    },
    { immediate: true },
  )

  function stop(): void {
    if (stopped) return
    stopped = true
    stopWatch()
    release()
  }

  if (getCurrentScope()) onScopeDispose(stop)
  return { stop }
}
```

这里没有访问全局 `window`；SSR 时调用者传 null 即无绑定。DOM template ref 首次为 null，挂载赋值后 watcher 自动绑定。默认 flush 足够；若依赖于刚 patch 的 ref，可用调用层确保 mounted，通常不必强制 post。

### 3. Spy 测试

```ts
import { effectScope, nextTick, ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import { useEventListener } from './useEventListener'

class SpyTarget extends EventTarget {
  readonly added: Array<{ type: string; listener: EventListenerOrEventListenerObject; capture: boolean }> = []
  readonly removed: Array<{ type: string; listener: EventListenerOrEventListenerObject; capture: boolean }> = []

  override addEventListener(
    type: string,
    callback: EventListenerOrEventListenerObject | null,
    options?: boolean | AddEventListenerOptions,
  ): void {
    if (callback) this.added.push({
      type,
      listener: callback,
      capture: typeof options === 'boolean' ? options : Boolean(options?.capture),
    })
    super.addEventListener(type, callback, options)
  }

  override removeEventListener(
    type: string,
    callback: EventListenerOrEventListenerObject | null,
    options?: boolean | EventListenerOptions,
  ): void {
    if (callback) this.removed.push({
      type,
      listener: callback,
      capture: typeof options === 'boolean' ? options : Boolean(options?.capture),
    })
    super.removeEventListener(type, callback, options)
  }
}

describe('useEventListener', () => {
  it('moves one stable listener from A to B', async () => {
    const a = new SpyTarget()
    const b = new SpyTarget()
    const target = ref<EventTarget | null>(a)
    const callback = vi.fn()
    const handle = useEventListener<Event>(target, 'ping', callback)

    target.value = b
    await nextTick()
    expect(a.added).toHaveLength(1)
    expect(a.removed).toHaveLength(1)
    expect(b.added).toHaveLength(1)
    expect(a.removed[0]?.listener).toBe(a.added[0]?.listener)
    handle.stop()
    expect(b.removed).toHaveLength(1)
  })

  it('rebinds when capture changes with symmetric removal', async () => {
    const target = new SpyTarget()
    const capture = ref(false)
    const handle = useEventListener(target, 'ping', () => {}, () => ({
      capture: capture.value,
    }))
    capture.value = true
    await nextTick()
    expect(target.removed[0]?.capture).toBe(false)
    expect(target.added[1]?.capture).toBe(true)
    handle.stop()
  })

  it('is null-safe and binds later', async () => {
    const current = ref<EventTarget | null>(null)
    const target = new SpyTarget()
    const handle = useEventListener(current, 'ping', () => {})
    expect(target.added).toHaveLength(0)
    current.value = target
    await nextTick()
    expect(target.added).toHaveLength(1)
    handle.stop()
  })

  it('scope disposal removes the binding', () => {
    const target = new SpyTarget()
    const scope = effectScope()
    scope.run(() => useEventListener(target, 'ping', () => {}))
    scope.stop()
    expect(target.removed).toHaveLength(1)
  })

  it('manual stop is permanent and idempotent', async () => {
    const first = new SpyTarget()
    const second = new SpyTarget()
    const target = ref<EventTarget | null>(first)
    const handle = useEventListener(target, 'ping', () => {})
    handle.stop()
    handle.stop()
    target.value = second
    await nextTick()
    expect(first.removed).toHaveLength(1)
    expect(second.added).toHaveLength(0)
  })
})
```

### 4. 常见错解与边界

- remove 时传了另一个箭头函数：listener 身份不同，无法移除。
- 只在 onUnmounted remove：target 改变后旧 target 仍绑定。
- stop 只 unbind、不停 watcher：输入下一次变化又复活。
- 用 deep watch 整个 options：不必要重绑；只读取实际影响绑定的字段。
- signal 被 abort 后，同一个 signal 不能“复活”；options 应换新 signal 才能重绑。
- 如果要 KeepAlive pause/resume，应新增显式 `paused/disposed` 状态，并在 activated/deactivated 调用；不要把 pause 实现成永久 stop。

---

## 练习 2 参考答案：singleflight 资源客户端

### 1. 所有权图

```text
ResourceClient（按 SSR request / browser app 创建）
├─ cache: key → completed value + updatedAt
├─ entries: key → subscribers + generation + optional inFlight
│                  ├─ handle A state
│                  ├─ handle B state
│                  └─ one AbortController / Promise
└─ watcher stops

detach A：只删除 A
detach 最后一个：abort inFlight、generation++
invalidate/refresh：generation++、abort old、同 key 当前订阅者共享 new flight
dispose client：停止全部 watcher、abort 全部、清空 Map
```

### 2. 实现

```ts
// resource-client.ts
import {
  getCurrentScope,
  onScopeDispose,
  readonly,
  shallowRef,
  toValue,
  watch,
  type DeepReadonly,
  type MaybeRefOrGetter,
  type Ref,
  type WatchStopHandle,
} from 'vue'

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

export class DisposedClientError extends Error {
  constructor() {
    super('ResourceClient has been disposed')
    this.name = 'DisposedClientError'
  }
}

interface CacheEntry<T> { data: T; updatedAt: number }
interface Subscriber<T> { state: Ref<ResourceState<T>>; key: string | null }
interface Flight {
  generation: number
  controller: AbortController
  promise: Promise<void>
}
interface KeyEntry<T> {
  key: string
  generation: number
  subscribers: Set<Subscriber<T>>
  flight: Flight | null
}

function normalizeKey(key: string | null): string | null {
  const normalized = key?.trim() ?? ''
  return normalized.length ? normalized : null
}

function toError(cause: unknown): Error {
  return cause instanceof Error ? cause : new Error(String(cause))
}

function isAbortError(cause: unknown): boolean {
  return cause instanceof DOMException && cause.name === 'AbortError'
}

export function createResourceClient<T>(options: {
  loader(key: string, signal: AbortSignal): Promise<T>
  ttlMs: number
  now?: () => number
}): ResourceClient<T> {
  if (!Number.isFinite(options.ttlMs) || options.ttlMs < 0) {
    throw new RangeError('ttlMs must be a finite non-negative number')
  }

  const now = options.now ?? Date.now
  const cache = new Map<string, CacheEntry<T>>()
  const entries = new Map<string, KeyEntry<T>>()
  const watcherStops = new Set<WatchStopHandle>()
  let disposed = false

  function assertAlive(): void {
    if (disposed) throw new DisposedClientError()
  }

  function getEntry(key: string): KeyEntry<T> {
    let entry = entries.get(key)
    if (!entry) {
      entry = { key, generation: 0, subscribers: new Set(), flight: null }
      entries.set(key, entry)
    }
    return entry
  }

  function previousOf(state: ResourceState<T>): T | null {
    switch (state.status) {
      case 'success': return state.data
      case 'loading': return state.previous
      case 'error': return state.previous
      case 'idle': return null
    }
  }

  function broadcastLoading(entry: KeyEntry<T>): void {
    const cached = cache.get(entry.key)?.data ?? null
    for (const subscriber of entry.subscribers) {
      subscriber.state.value = {
        status: 'loading',
        previous: cached ?? previousOf(subscriber.state.value),
      }
    }
  }

  function startFlight(entry: KeyEntry<T>, force: boolean): void {
    assertAlive()
    if (entry.flight && !force) {
      broadcastLoading(entry)
      return
    }

    if (entry.flight) entry.flight.controller.abort()
    const generation = ++entry.generation
    const controller = new AbortController()
    broadcastLoading(entry)

    const promise = Promise.resolve()
      .then(() => options.loader(entry.key, controller.signal))
      .then(data => {
        if (
          disposed
          || controller.signal.aborted
          || entry.generation !== generation
        ) return

        const updatedAt = now()
        cache.set(entry.key, { data, updatedAt })
        for (const subscriber of entry.subscribers) {
          subscriber.state.value = { status: 'success', data, updatedAt }
        }
      })
      .catch((cause: unknown) => {
        if (
          disposed
          || controller.signal.aborted
          || entry.generation !== generation
          || isAbortError(cause)
        ) return

        const error = toError(cause)
        for (const subscriber of entry.subscribers) {
          subscriber.state.value = {
            status: 'error',
            error,
            previous: previousOf(subscriber.state.value),
          }
        }
      })
      .finally(() => {
        if (entry.flight?.generation === generation) entry.flight = null
        if (entry.subscribers.size === 0 && !entry.flight) entries.delete(entry.key)
      })

    entry.flight = { generation, controller, promise }
  }

  function attach(subscriber: Subscriber<T>, key: string, force: boolean): void {
    const entry = getEntry(key)
    subscriber.key = key
    entry.subscribers.add(subscriber)

    if (force) {
      cache.delete(key)
      startFlight(entry, true)
      return
    }

    const cached = cache.get(key)
    if (cached && now() - cached.updatedAt < options.ttlMs) {
      subscriber.state.value = {
        status: 'success', data: cached.data, updatedAt: cached.updatedAt,
      }
      return
    }

    if (entry.flight) {
      subscriber.state.value = {
        status: 'loading', previous: cached?.data ?? null,
      }
      return
    }
    startFlight(entry, false)
  }

  function detach(subscriber: Subscriber<T>): void {
    const key = subscriber.key
    subscriber.key = null
    if (!key) return
    const entry = entries.get(key)
    if (!entry) return
    entry.subscribers.delete(subscriber)
    if (entry.subscribers.size > 0) return

    if (entry.flight) {
      entry.generation++
      entry.flight.controller.abort()
      entry.flight = null
    }
    entries.delete(key)
  }

  function invalidate(rawKey: string): void {
    assertAlive()
    const key = normalizeKey(rawKey)
    if (!key) return
    cache.delete(key)
    const entry = entries.get(key)
    if (!entry || entry.subscribers.size === 0) return
    startFlight(entry, true)
  }

  function useResource(
    keySource: MaybeRefOrGetter<string | null>,
  ): ResourceHandle<T> {
    assertAlive()
    if (!getCurrentScope()) {
      throw new Error('useResource must be called inside an active effect scope')
    }

    const state = shallowRef<ResourceState<T>>({ status: 'idle' })
    const subscriber: Subscriber<T> = { state, key: null }
    const refreshVersion = shallowRef(0)

    const stop = watch(
      [() => normalizeKey(toValue(keySource)), refreshVersion],
      ([key, version], previous, onCleanup) => {
        const force = previous !== undefined
          && key !== null
          && key === previous[0]
          && version !== previous[1]

        if (!key) {
          state.value = { status: 'idle' }
          return
        }

        attach(subscriber, key, force)
        onCleanup(() => detach(subscriber))
      },
      { immediate: true },
    )

    watcherStops.add(stop)
    onScopeDispose(() => {
      stop()
      watcherStops.delete(stop)
    })

    return {
      state: readonly(state) as DeepReadonly<Ref<ResourceState<T>>>,
      refresh(): void {
        assertAlive()
        refreshVersion.value++
      },
    }
  }

  function dispose(): void {
    if (disposed) return
    disposed = true
    for (const stop of [...watcherStops]) stop()
    watcherStops.clear()
    for (const entry of entries.values()) {
      entry.generation++
      entry.flight?.controller.abort()
      entry.subscribers.clear()
      entry.flight = null
    }
    entries.clear()
    cache.clear()
  }

  return { useResource, invalidate, dispose }
}
```

### 3. 一个重要审查点

上面 `startFlight(entry, true)` 会让**所有**当前订阅者共享新一轮请求，因为 flight 存在 key entry 上，而不是 handle 上。一个 handle refresh 不是为自己开旁路请求；这正是公共契约的 singleflight 语义。

### 4. 关键时序测试

```ts
import { effectScope, nextTick, ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import { createResourceClient, DisposedClientError } from './resource-client'

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

async function flushPromises(): Promise<void> {
  await Promise.resolve()
  await Promise.resolve()
  await Promise.resolve()
}

it('shares one flight across three subscribers', async () => {
  const pending = deferred<string>()
  const loader = vi.fn(() => pending.promise)
  const client = createResourceClient({ loader, ttlMs: 1_000 })
  const scopes = [effectScope(), effectScope(), effectScope()]
  const handles = scopes.map(scope => scope.run(() => client.useResource(' project-1 '))!)

  await flushPromises()
  expect(loader).toHaveBeenCalledTimes(1)
  pending.resolve('P1')
  await flushPromises()
  expect(handles.every(handle => handle.state.value.status === 'success')).toBe(true)

  scopes.forEach(scope => scope.stop())
  client.dispose()
})

it('aborts only after the final subscriber leaves', async () => {
  let signal: AbortSignal | undefined
  const pending = deferred<string>()
  const client = createResourceClient({
    loader: (_key, nextSignal) => { signal = nextSignal; return pending.promise },
    ttlMs: 0,
  })
  const a = effectScope()
  const b = effectScope()
  a.run(() => client.useResource('p1'))
  b.run(() => client.useResource('p1'))
  await flushPromises()

  a.stop()
  expect(signal?.aborted).toBe(false)
  b.stop()
  expect(signal?.aborted).toBe(true)
  client.dispose()
})

it('uses fresh cache and reloads after fake time expires', async () => {
  let time = 100
  const loader = vi.fn().mockResolvedValue('P1')
  const client = createResourceClient({ loader, ttlMs: 50, now: () => time })
  const first = effectScope()
  first.run(() => client.useResource('p1'))
  await flushPromises()
  first.stop()

  time = 120
  const second = effectScope()
  second.run(() => client.useResource('p1'))
  await flushPromises()
  expect(loader).toHaveBeenCalledTimes(1)
  second.stop()

  time = 151
  const third = effectScope()
  third.run(() => client.useResource('p1'))
  await flushPromises()
  expect(loader).toHaveBeenCalledTimes(2)
  third.stop()
  client.dispose()
})

it('rejects an old result after invalidate', async () => {
  const old = deferred<string>()
  const fresh = deferred<string>()
  const loader = vi.fn()
    .mockReturnValueOnce(old.promise)
    .mockReturnValueOnce(fresh.promise)
  const client = createResourceClient({ loader, ttlMs: 1_000 })
  const scope = effectScope()
  const handle = scope.run(() => client.useResource('p1'))!
  await flushPromises()

  client.invalidate('p1')
  await flushPromises()
  fresh.resolve('fresh')
  await flushPromises()
  old.resolve('old')
  await flushPromises()
  expect(handle.state.value).toMatchObject({ status: 'success', data: 'fresh' })
  scope.stop()
  client.dispose()
})

it('isolates two client instances', async () => {
  const loader = vi.fn().mockResolvedValue('P1')
  const first = createResourceClient({ loader, ttlMs: 1_000 })
  const second = createResourceClient({ loader, ttlMs: 1_000 })
  const a = effectScope()
  const b = effectScope()
  a.run(() => first.useResource('p1'))
  b.run(() => second.useResource('p1'))
  await flushPromises()
  expect(loader).toHaveBeenCalledTimes(2)
  a.stop(); b.stop(); first.dispose(); second.dispose()
})

it('disposes idempotently and rejects future work', () => {
  const client = createResourceClient<string>({
    loader: async () => 'x', ttlMs: 0,
  })
  client.dispose()
  client.dispose()
  expect(() => client.invalidate('x')).toThrow(DisposedClientError)
  const scope = effectScope()
  expect(() => scope.run(() => client.useResource('x'))).toThrow(DisposedClientError)
  scope.stop()
})
```

还应补：当前 flight reject 广播 error、AbortError 不显示、refresh 两个订阅者仍只新增一次 loader、key ref 从 A→B、空 key idle、同步 throw、TTL=0。

### 5. 常见错解

- in-flight Map 放在模块全局：不同 SSR 请求共享认证结果。
- handle stop 就 abort controller：破坏其他订阅者。
- Promise resolve 无 generation 检查：被 invalidate 的旧请求重新写回缓存。
- 错误也长期缓存：临时网络故障变成稳定失败；如需负缓存必须单独定义短 TTL 和错误分类。
- cache key 只含 projectId：多租户同 id 串数据。实际 key 至少包含 tenant、身份/permission scope、locale、影响响应的版本。
- `ttlMs=0` 仍在同一进行中请求 singleflight；完成后新订阅立即重取。这正好说明 cache 与 singleflight 是两层。

### 6. 生产扩展边界

- 真实 query client 还要 stale time/cache time、后台 revalidate、重试退避、窗口聚焦刷新、分页、乐观更新、SSR dehydration；不要无止境扩张自研版本。
- loader 的认证上下文必须属于 client 实例；SSR 每个请求建 client，客户端 hydration 后再拥有浏览器级实例。
- Map 上限 1,000 仍需淘汰策略；本实现只在无 subscriber 且无 flight 时删 entry，cache 则直到 invalidate/dispose。生产版要有 LRU/cacheTime。
- 共享只适合同 key 的幂等读取。创建订单等写操作需要 idempotency key 和独立提交状态机。

完成后请重新画一次引用计数时间线：A/B/C attach，只启动一次；A、B detach 不 abort；C detach 才 abort。能解释这条线，才真正理解“资源所有权”而不只是抄代码。
