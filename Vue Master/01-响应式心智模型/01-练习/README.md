# 第 01 章练习：依赖内核与搜索竞态

> 只做两题。先独立写出“契约、状态图、失败语义”，再写代码。不要直接看答案。

## 练习 1：实现一个能切换动态依赖的最小响应式内核（机制题）

### 背景

你要给团队做一次响应式原理演示。只实现对象属性的 `reactive` 与 `effect`，但不能停留在“改值能重跑”：条件分支切换后，旧依赖必须被清除；同一个 effect 在一次同步批量写入中只能进入队列一次。

### 公共契约

```ts
export interface StopHandle {
  stop(): void
}

export interface EffectOptions {
  scheduler?: (job: () => void) => void
}

export declare function reactive<T extends object>(raw: T): T

export declare function effect(
  fn: () => void,
  options?: EffectOptions,
): StopHandle

export declare function queueJob(job: () => void): void
export declare function nextFlush(): Promise<void>
```

### 必须支持

1. 依赖按 `target + key` 区分；没有活动 effect 的读取不建边。
2. effect 每次重跑前清除旧依赖，支持：`ok ? text : fallback`。
3. effect 嵌套后能恢复父 effect。
4. 写入 `Object.is(old, next)` 相等的值不触发。
5. effect 执行时写入自己的依赖，不得同步递归到栈溢出；至少跳过当前活动 effect。
6. `stop()` 后从所有依赖集合移除，且重复调用安全。
7. `queueJob` 使用微任务批处理；同一个函数在一轮只执行一次。

### 规模与限制

- 只处理普通对象的 `get/set`；无需数组、Map、迭代键、computed、readonly。
- 单个对象最多 1,000 个键、100 个 effect；优先保证语义清晰。
- 禁止使用 Vue、RxJS 或其他响应式库。
- TypeScript `strict` 下通过；禁止 `any`。

### 验收用例

```ts
const state = reactive({ ok: true, text: 'A', fallback: 'B' })
let rendered = ''
let runs = 0

const handle = effect(() => {
  runs++
  rendered = state.ok ? state.text : state.fallback
}, { scheduler: queueJob })

state.text = 'A1'
state.text = 'A2'
await nextFlush()
// rendered === 'A2'，runs === 2（首次 + 本轮一次）

state.ok = false
await nextFlush()
state.text = 'SHOULD_NOT_TRIGGER'
await nextFlush()
// rendered === 'B'，runs === 3；旧 text 依赖已移除

state.fallback = 'B2'
await nextFlush()
// rendered === 'B2'，runs === 4

handle.stop()
handle.stop()
state.fallback = 'B3'
await nextFlush()
// rendered 仍为 'B2'
```

### 交付物

- `mini-reactivity.ts`；
- 至少 6 个单元测试，覆盖动态依赖、批处理、嵌套、相等写入、自触发保护、stop；
- 一张不超过 20 行的依赖图说明。

### 发散思考（不要求实现）

- 为什么真实 Vue 还需要处理新增/删除属性、数组 length 和集合迭代？
- 如果 scheduler 收到的 job 每次都是新闭包，Set 去重为什么会失效？

---

## 练习 2：实现生产语义明确的 `useLatestSearch`（生产题）

### 事故场景

后台会员页支持输入联想。用户快速输入时，旧请求可能晚返回；组件关闭时请求仍在运行；空白查询不应请求；AbortError 不应出现红色错误提示；新查询期间要保留上一屏结果，避免列表闪空。

### 公共契约

```ts
import type { MaybeRefOrGetter, DeepReadonly, Ref } from 'vue'

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

export declare function useLatestSearch<T>(
  query: MaybeRefOrGetter<string>,
  searcher: (query: string, context: SearchContext) => Promise<readonly T[]>,
): LatestSearch<T>
```

### 业务规则

1. 查询先 `trim()`；空字符串进入 `idle`，保留空数组，不调用 `searcher`。
2. 查询变化立即进入 `loading`，并保留最近一次成功数据。
3. 并发语义为 latest-wins：旧请求即使无法真正取消，也不得提交结果或错误。
4. 每轮传入新的 `AbortSignal`；新一轮和作用域销毁时 abort 旧请求。
5. `AbortError` 与失效请求的 reject 都静默丢弃；当前有效请求的其他错误进入 `error`。
6. `retry()` 重试当前规范化查询，即使字符串本身没变化。
7. 状态只读；不得把内部可写 ref 暴露给调用方。

### 规模与错误语义

- 输入峰值每秒 20 次，本题不做 debounce；后续可在输入层增加。
- 单次最多 100 条结果。
- `searcher` 可能不理会 signal、可能同步 throw、可能乱序 resolve/reject。
- 不做缓存与自动重试；这些语义不能悄悄混入基础版本。

### 验收

- 用两个可控 Promise，让第二次先 resolve、第一次后 resolve，最终只能显示第二次。
- 当前请求失败显示 error；上一轮失效请求失败不改变状态。
- 查询变空会取消进行中请求并进入 idle。
- effect scope `stop()` 后请求被 abort，后续完成不得写状态。
- `retry()` 会产生新 signal 和新一代任务。

### 交付物

- `useLatestSearch.ts`；
- Vitest 测试，禁止真实网络与真实 sleep；
- 120 字以内说明：为什么同时使用 abort 和 generation token。

### 发散思考

- 若产品要求 300ms debounce，应放在 composable 内还是输入适配层？各自影响什么？
- 若这是“创建订单”而不是搜索，latest-wins 为什么危险？你会改成什么并发协议？
