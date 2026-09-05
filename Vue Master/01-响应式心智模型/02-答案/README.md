# 第 01 章答案：依赖内核与搜索竞态

> 这不是唯一实现。先核对语义，再比较代码。真正的答案是你能解释每一条边何时建立、删除，以及每一个异步结果为何允许或禁止提交。

## 练习 1 参考答案：最小响应式内核

### 1. 设计推导

每个 effect 必须反向记录自己加入过哪些依赖集合：

```text
bucket: target → key → Dep(Set<ReactiveEffect>)
                            ↑
ReactiveEffect.deps: [Dep, Dep, ...]
```

正向索引用于 trigger 找订阅者，反向索引用于重跑/stop 时清理。嵌套 effect 用栈恢复；调度器接收稳定的 `job` 函数，否则 `Set` 无法去重。

### 2. 核心实现

```ts
// mini-reactivity.ts
type Dep = Set<ReactiveEffect>
type KeyToDepsMap = Map<PropertyKey, Dep>

export interface StopHandle {
  stop(): void
}

export interface EffectOptions {
  scheduler?: (job: () => void) => void
}

const bucket = new WeakMap<object, KeyToDepsMap>()
const effectStack: ReactiveEffect[] = []
let activeEffect: ReactiveEffect | undefined

class ReactiveEffect {
  readonly deps: Dep[] = []
  readonly job: () => void
  active = true

  constructor(
    private readonly fn: () => void,
    private readonly scheduler?: (job: () => void) => void,
  ) {
    // job 身份永久稳定，queue Set 才能去重。
    this.job = () => this.run()
  }

  run(): void {
    if (!this.active) {
      // 手动拿到 job 后 stop 再调用，可执行原函数但不再追踪。
      this.fn()
      return
    }

    cleanupEffect(this)
    effectStack.push(this)
    activeEffect = this
    try {
      this.fn()
    } finally {
      effectStack.pop()
      activeEffect = effectStack.at(-1)
    }
  }

  notify(): void {
    if (this === activeEffect) return
    if (this.scheduler) this.scheduler(this.job)
    else this.run()
  }

  stop(): void {
    if (!this.active) return
    cleanupEffect(this)
    this.active = false
  }
}

function cleanupEffect(effect: ReactiveEffect): void {
  for (const dep of effect.deps) dep.delete(effect)
  effect.deps.length = 0
}

function track(target: object, key: PropertyKey): void {
  const effect = activeEffect
  if (!effect || !effect.active) return

  let depsMap = bucket.get(target)
  if (!depsMap) {
    depsMap = new Map()
    bucket.set(target, depsMap)
  }

  let dep = depsMap.get(key)
  if (!dep) {
    dep = new Set()
    depsMap.set(key, dep)
  }

  if (dep.has(effect)) return
  dep.add(effect)
  effect.deps.push(dep)
}

function trigger(target: object, key: PropertyKey): void {
  const dep = bucket.get(target)?.get(key)
  if (!dep) return

  // run 会修改原 dep，必须快照。
  const effectsToRun = new Set(dep)
  for (const effect of effectsToRun) effect.notify()
}

export function reactive<T extends object>(raw: T): T {
  return new Proxy(raw, {
    get(target, key, receiver) {
      track(target, key)
      return Reflect.get(target, key, receiver)
    },
    set(target, key, value, receiver) {
      const previous = Reflect.get(target, key, receiver) as unknown
      const ok = Reflect.set(target, key, value, receiver)
      if (ok && !Object.is(previous, value)) trigger(target, key)
      return ok
    },
  })
}

export function effect(
  fn: () => void,
  options: EffectOptions = {},
): StopHandle {
  const reactiveEffect = new ReactiveEffect(fn, options.scheduler)
  reactiveEffect.run()
  return { stop: () => reactiveEffect.stop() }
}

const queue = new Set<() => void>()
let currentFlush: Promise<void> | null = null

export function queueJob(job: () => void): void {
  queue.add(job)
  if (currentFlush) return

  currentFlush = Promise.resolve().then(() => {
    try {
      // 快照允许执行中的 job 再为下一阶段排任务；本题简化为同轮处理。
      for (const queuedJob of [...queue]) queuedJob()
    } finally {
      queue.clear()
      currentFlush = null
    }
  })
}

export function nextFlush(): Promise<void> {
  return currentFlush ?? Promise.resolve()
}
```

### 3. 关键测试

```ts
import { describe, expect, it, vi } from 'vitest'
import { effect, nextFlush, queueJob, reactive } from './mini-reactivity'

describe('mini reactivity', () => {
  it('batches a stable effect job', async () => {
    const state = reactive({ n: 0 })
    const render = vi.fn(() => void state.n)
    effect(render, { scheduler: queueJob })

    state.n++
    state.n++
    state.n++
    expect(render).toHaveBeenCalledTimes(1)

    await nextFlush()
    expect(render).toHaveBeenCalledTimes(2)
  })

  it('removes stale conditional dependencies', async () => {
    const state = reactive({ ok: true, a: 'A', b: 'B' })
    const observed: string[] = []
    effect(() => observed.push(state.ok ? state.a : state.b), {
      scheduler: queueJob,
    })

    state.ok = false
    await nextFlush()
    state.a = 'A2'
    await nextFlush()

    expect(observed).toEqual(['A', 'B'])

    state.b = 'B2'
    await nextFlush()
    expect(observed).toEqual(['A', 'B', 'B2'])
  })

  it('restores parent effect after a nested effect', () => {
    const state = reactive({ outer: 0, inner: 0, tail: 0 })
    let innerCreated = false
    const outerRun = vi.fn(() => {
      void state.outer
      if (!innerCreated) {
        innerCreated = true
        effect(() => void state.inner)
      }
      // 嵌套执行结束后，这个读取仍应属于 outer。
      void state.tail
    })
    effect(outerRun)
    state.tail++
    expect(outerRun).toHaveBeenCalledTimes(2)
  })

  it('ignores Object.is-equal writes', () => {
    const state = reactive({ n: Number.NaN })
    const run = vi.fn(() => void state.n)
    effect(run)
    state.n = Number.NaN
    expect(run).toHaveBeenCalledTimes(1)
  })

  it('does not synchronously trigger itself', () => {
    const state = reactive({ n: 0 })
    expect(() => {
      effect(() => {
        if (state.n < 1) state.n++
      })
    }).not.toThrow()
    expect(state.n).toBe(1)
  })

  it('stop is idempotent and detaches dependencies', () => {
    const state = reactive({ n: 0 })
    const run = vi.fn(() => void state.n)
    const handle = effect(run)
    handle.stop()
    handle.stop()
    state.n++
    expect(run).toHaveBeenCalledTimes(1)
  })
})
```

### 4. 常见错解

- 每次 scheduler 都传 `() => effect.run()`：函数身份不同，同轮无法去重。
- 只清 dependency Set，不清 `effect.deps`：反向表一直增长。
- trigger 直接遍历原 Set：run 先删除再添加自己，可能被重复访问。
- 嵌套 effect 执行完把 `activeEffect = undefined`：父 effect 后续读取丢失。
- `stop()` 只设置 boolean：依赖集合仍强引用 effect，后续 trigger 还需遍历垃圾项。

### 5. 生产限制

这不是可替代 Vue 的实现。它没有代理缓存、深层转换、数组语义、`has/ownKeys/deleteProperty`、Map/Set、computed 优先级、错误处理、递归策略以及 Vue 调度器的父子顺序。练习价值在于建立因果模型，而不是造框架。

---

## 练习 2 参考答案：`useLatestSearch`

### 1. 先把语义写成提交门卫

每轮任务只有同时满足以下条件才能提交：

```text
scope 仍活着
AND 本轮未因 watcher invalidation 失效
AND generation === 全局最新 generation
AND signal 未被 abort
```

Abort 尽量节约资源，generation 保证正确性。两者职责不同。

### 2. 实现

```ts
// useLatestSearch.ts
import {
  onScopeDispose,
  readonly,
  shallowRef,
  toValue,
  watch,
  type DeepReadonly,
  type MaybeRefOrGetter,
  type Ref,
} from 'vue'

export type SearchState<T> =
  | { status: 'idle'; data: readonly T[] }
  | { status: 'loading'; data: readonly T[]; query: string }
  | { status: 'success'; data: readonly T[]; query: string }
  | { status: 'error'; data: readonly T[]; query: string; error: Error }

export interface SearchContext {
  signal: AbortSignal
}

export interface LatestSearch<T> {
  state: DeepReadonly<Ref<SearchState<T>>>
  retry(): void
}

function toError(cause: unknown): Error {
  return cause instanceof Error ? cause : new Error(String(cause))
}

function isAbortError(cause: unknown): boolean {
  return cause instanceof DOMException && cause.name === 'AbortError'
}

export function useLatestSearch<T>(
  query: MaybeRefOrGetter<string>,
  searcher: (query: string, context: SearchContext) => Promise<readonly T[]>,
): LatestSearch<T> {
  const state = shallowRef<SearchState<T>>({ status: 'idle', data: [] })
  const retryToken = shallowRef(0)
  let generation = 0
  let scopeAlive = true

  onScopeDispose(() => {
    scopeAlive = false
    generation++ // 即使底层 Promise 无法取消，也关闭提交权限。
  })

  watch(
    [() => toValue(query).trim(), retryToken],
    async ([normalizedQuery], _previous, onCleanup) => {
      const currentGeneration = ++generation
      let active = true
      const controller = new AbortController()

      onCleanup(() => {
        active = false
        controller.abort()
      })

      if (!normalizedQuery) {
        state.value = { status: 'idle', data: [] }
        return
      }

      const previousData = state.value.data
      state.value = {
        status: 'loading',
        data: previousData,
        query: normalizedQuery,
      }

      const canCommit = (): boolean =>
        scopeAlive
        && active
        && currentGeneration === generation
        && !controller.signal.aborted

      try {
        // Promise.resolve 同时吸收 searcher 的同步 throw 和 thenable。
        const rows = await Promise.resolve().then(() => searcher(
          normalizedQuery,
          { signal: controller.signal },
        ))

        if (!canCommit()) return
        state.value = {
          status: 'success',
          data: rows,
          query: normalizedQuery,
        }
      } catch (cause: unknown) {
        if (!canCommit() || isAbortError(cause)) return
        state.value = {
          status: 'error',
          data: previousData,
          query: normalizedQuery,
          error: toError(cause),
        }
      }
    },
    { immediate: true },
  )

  return {
    state: readonly(state),
    retry: () => { retryToken.value++ },
  }
}
```

这里把 `retryToken` 作为第二个显式 source。只改相同查询字符串时，watch 不会触发；token 让 retry 成为一个明确事件。

### 3. 可控异步测试

```ts
import { effectScope, nextTick, ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import { useLatestSearch } from './useLatestSearch'

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
}

describe('useLatestSearch', () => {
  it('commits only the latest result', async () => {
    const first = deferred<readonly string[]>()
    const second = deferred<readonly string[]>()
    const searcher = vi.fn()
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise)
    const query = ref('vue')
    const scope = effectScope()
    const api = scope.run(() => useLatestSearch(query, searcher))!

    await flushPromises()
    query.value = 'vue 3'
    await nextTick()
    await flushPromises()

    second.resolve(['new'])
    await flushPromises()
    expect(api.state.value).toMatchObject({ status: 'success', data: ['new'] })

    first.resolve(['old'])
    await flushPromises()
    expect(api.state.value).toMatchObject({ status: 'success', data: ['new'] })
    scope.stop()
  })

  it('ignores a stale rejection', async () => {
    const first = deferred<readonly string[]>()
    const second = deferred<readonly string[]>()
    const query = ref('a')
    const searcher = vi.fn()
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise)
    const scope = effectScope()
    const api = scope.run(() => useLatestSearch(query, searcher))!

    await flushPromises()
    query.value = 'ab'
    await nextTick()
    second.resolve(['AB'])
    await flushPromises()
    first.reject(new Error('stale failure'))
    await flushPromises()

    expect(api.state.value).toMatchObject({ status: 'success', data: ['AB'] })
    scope.stop()
  })

  it('aborts when query becomes blank', async () => {
    const pending = deferred<readonly string[]>()
    let capturedSignal: AbortSignal | undefined
    const query = ref('vue')
    const scope = effectScope()
    const api = scope.run(() => useLatestSearch(query, (_q, context) => {
      capturedSignal = context.signal
      return pending.promise
    }))!

    await flushPromises()
    query.value = '   '
    await nextTick()

    expect(capturedSignal?.aborted).toBe(true)
    expect(api.state.value).toEqual({ status: 'idle', data: [] })
    scope.stop()
  })

  it('aborts on scope disposal and rejects later commits', async () => {
    const pending = deferred<readonly string[]>()
    let signal: AbortSignal | undefined
    const scope = effectScope()
    const api = scope.run(() => useLatestSearch('vue', (_q, context) => {
      signal = context.signal
      return pending.promise
    }))!

    await flushPromises()
    scope.stop()
    expect(signal?.aborted).toBe(true)

    pending.resolve(['too late'])
    await flushPromises()
    expect(api.state.value.status).not.toBe('success')
  })

  it('retry starts a new generation and signal', async () => {
    const signals: AbortSignal[] = []
    const searcher = vi.fn((_q: string, context: { signal: AbortSignal }) => {
      signals.push(context.signal)
      return Promise.resolve<readonly string[]>([])
    })
    const scope = effectScope()
    const api = scope.run(() => useLatestSearch('vue', searcher))!
    await flushPromises()
    api.retry()
    await nextTick()
    await flushPromises()

    expect(searcher).toHaveBeenCalledTimes(2)
    expect(signals[0]).not.toBe(signals[1])
    scope.stop()
  })
})
```

### 4. 为什么不能只有 abort

`AbortController` 是资源协作协议：底层任务可以忽略 signal，请求也可能在 abort 前已经完成。generation 是提交协议：不管任务能否取消，只有最新一代能写状态。两者结合，前者减少浪费，后者保证 latest-wins 正确性。

### 5. 常见错解

- 只比较 query 字符串：用户可能输入 A→B→A，第一轮 A 会误判为当前。
- catch 时无条件写 error：被取消的旧请求覆盖新成功状态。
- 每次 loading 清空 data：产生不必要闪烁，也丢失 stale-while-revalidate 体验。
- 返回原始 `state` ref：调用方能伪造任意状态，破坏不变量。
- 在 `await` 后注册 cleanup：可能已经错过 watcher 的同步注册窗口。
- 用 debounce 当竞态修复：debounce 减少请求数，不能证明不会乱序。

### 6. 生产限制与扩展

- 真实接口响应必须从 `unknown` 做运行时 schema 校验。
- debounce、缓存、分页合并、重试退避、离线策略都应作为显式层，不应悄悄改变基础契约。
- 若多个组件查询相同 key，需要 query cache/singleflight；本实现是单消费者作用域。
- 写请求必须考虑幂等键和服务端事务，不能采用“旧结果直接丢弃”掩盖已经发生的副作用。
- 如果要在 SSR 执行，fetch 依赖与缓存必须按请求隔离，不能在模块全局保存 mutable generation。

完成后，合上答案，用自己的话重建两张图：`target/key/effect` 双向索引，以及 `abort + generation + scopeAlive` 三层提交门卫。
