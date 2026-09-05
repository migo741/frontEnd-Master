# 第 19 章答案：用状态表、代码与测试证明 Renderer 行为

> 参考答案基于 Vue Core `v3.5.42`。代码是教学模型，不复制或替代 Vue 私有 runtime。生产修复应使用稳定 public API，并用集成测试保护可观察行为。

## 练习 1 参考答案：Keyed 列表状态保持与最小移动审计

### 1. 先写身份与算法不变量

身份契约：

```text
同一父级中，type + key 相同 → 可复用同一逻辑 VNode / 组件实例
key 相同但 type 不同       → 旧身份结束，新身份挂载
key 不同                   → 不得因 DOM 内容相似而复用组件状态
```

unknown middle 阶段保持：

1. `keyToNewIndexMap` 只描述新中段；
2. `newIndexToOldIndexMap[j] = 0` 表示新位置尚未匹配旧节点；
3. 非零值保存 `oldIndex + 1`；
4. 遍历旧中段后，所有旧节点要么 patch，要么 unmount；
5. 反向阶段后，所有新节点要么已复用且在正确位置，要么已 mount；
6. LIS 中的相对顺序不需要 move，其余复用节点才移动。

### 2. 手算 old → new

```text
old: A B C D E
new: A C B F E
```

头部同步 A：

```text
i = 1
```

尾部同步 E：

```text
e1 = 3
e2 = 3
```

所以：

```text
s1 = 1, e1 = 3  → old middle B C D
s2 = 1, e2 = 3  → new middle C B F
```

新 key map：

```ts
new Map([
  ['C', 1],
  ['B', 2],
  ['F', 3],
])
```

旧中段遍历表：

| prev | old index | new index | map | patched | max new index | moved | 动作 |
| --- | ---: | ---: | --- | ---: | ---: | --- | --- |
| 初始 | - | - | `[0,0,0]` | 0 | 0 | false | - |
| B | 1 | 2 | `[0,2,0]` | 1 | 2 | false | patch B |
| C | 2 | 1 | `[3,2,0]` | 2 | 2 | true | patch C |
| D | 3 | 无 | `[3,2,0]` | 2 | 2 | true | unmount D |

`[3,2,0]` 的 LIS 忽略 0。固定算法返回中段索引 `[1]`，对应 B。反向阶段：

| 中段索引 | 节点 | anchor | 动作 |
| ---: | --- | --- | --- |
| 2 | F | E | map 为 0，mount F before E |
| 1 | B | F | 在 LIS 中，不 move |
| 0 | C | B | 不在 LIS，move C before B |

完整动作集合：

```text
A: patch
B: patch，保留位置作为稳定骨架
C: patch + move before B
D: unmount
E: patch
F: mount before E
```

patch 动作的记录顺序可能随快速路径出现为 A、E、B、C；不要把源码遍历顺序误当最终 DOM 顺序。

### 3. 教学 tracer

```ts
export interface Child {
  key: string
  type: string
}

export type DiffOperation =
  | { kind: 'patch'; key: string }
  | { kind: 'mount'; key: string; before: string | null }
  | { kind: 'move'; key: string; before: string | null }
  | { kind: 'unmount'; key: string }

export interface DiffTrace {
  operations: DiffOperation[]
  newIndexToOldIndexMap: number[]
  lisIndices: number[]
}

function sameVNode(a: Child, b: Child): boolean {
  return a.key === b.key && a.type === b.type
}

function assertUnique(items: readonly Child[], label: string): void {
  const seen = new Set<string>()
  for (const item of items) {
    if (seen.has(item.key)) {
      throw new Error(`${label} contains duplicate key: ${item.key}`)
    }
    seen.add(item.key)
  }
}

/**
 * 返回 arr 中严格递增子序列所对应的 arr 索引。
 * 0 是“新节点”哨兵，不参加序列。
 */
export function getSequence(arr: readonly number[]): number[] {
  const predecessors = arr.slice()
  const result: number[] = []

  for (let i = 0; i < arr.length; i += 1) {
    const value = arr[i]
    if (value === 0) continue

    if (result.length === 0 || arr[result[result.length - 1]] < value) {
      if (result.length > 0) {
        predecessors[i] = result[result.length - 1]
      }
      result.push(i)
      continue
    }

    let low = 0
    let high = result.length
    while (low < high) {
      const middle = (low + high) >>> 1
      if (arr[result[middle]] < value) low = middle + 1
      else high = middle
    }

    if (value < arr[result[low]]) {
      if (low > 0) predecessors[i] = result[low - 1]
      result[low] = i
    }
  }

  let length = result.length
  if (length === 0) return []

  let cursor = result[length - 1]
  while (length > 0) {
    length -= 1
    result[length] = cursor
    cursor = predecessors[cursor]
  }
  return result
}

export function traceKeyedDiff(
  previous: readonly Child[],
  next: readonly Child[],
): DiffTrace {
  assertUnique(previous, 'previous')
  assertUnique(next, 'next')

  const operations: DiffOperation[] = []
  let left = 0
  let oldRight = previous.length - 1
  let newRight = next.length - 1

  while (
    left <= oldRight &&
    left <= newRight &&
    sameVNode(previous[left], next[left])
  ) {
    operations.push({ kind: 'patch', key: next[left].key })
    left += 1
  }

  while (
    left <= oldRight &&
    left <= newRight &&
    sameVNode(previous[oldRight], next[newRight])
  ) {
    operations.push({ kind: 'patch', key: next[newRight].key })
    oldRight -= 1
    newRight -= 1
  }

  if (left > oldRight) {
    const anchor = next[newRight + 1]?.key ?? null
    for (let i = left; i <= newRight; i += 1) {
      operations.push({ kind: 'mount', key: next[i].key, before: anchor })
    }
    return { operations, newIndexToOldIndexMap: [], lisIndices: [] }
  }

  if (left > newRight) {
    for (let i = left; i <= oldRight; i += 1) {
      operations.push({ kind: 'unmount', key: previous[i].key })
    }
    return { operations, newIndexToOldIndexMap: [], lisIndices: [] }
  }

  const newStart = left
  const toBePatched = newRight - newStart + 1
  const keyToNewIndex = new Map<string, number>()
  for (let i = newStart; i <= newRight; i += 1) {
    keyToNewIndex.set(next[i].key, i)
  }

  const newIndexToOldIndexMap = new Array<number>(toBePatched).fill(0)
  let patched = 0
  let maxNewIndexSoFar = 0
  let moved = false

  for (let oldIndex = left; oldIndex <= oldRight; oldIndex += 1) {
    const oldChild = previous[oldIndex]
    if (patched >= toBePatched) {
      operations.push({ kind: 'unmount', key: oldChild.key })
      continue
    }

    const newIndex = keyToNewIndex.get(oldChild.key)
    if (newIndex === undefined) {
      operations.push({ kind: 'unmount', key: oldChild.key })
      continue
    }

    const newChild = next[newIndex]
    if (oldChild.type !== newChild.type) {
      // type 改变意味着旧身份结束；保留 0，让反向阶段 mount 新身份。
      operations.push({ kind: 'unmount', key: oldChild.key })
      continue
    }

    newIndexToOldIndexMap[newIndex - newStart] = oldIndex + 1
    if (newIndex >= maxNewIndexSoFar) {
      maxNewIndexSoFar = newIndex
    } else {
      moved = true
    }
    operations.push({ kind: 'patch', key: newChild.key })
    patched += 1
  }

  const lisIndices = moved ? getSequence(newIndexToOldIndexMap) : []
  let lisCursor = lisIndices.length - 1

  for (let middleIndex = toBePatched - 1; middleIndex >= 0; middleIndex -= 1) {
    const nextIndex = newStart + middleIndex
    const nextChild = next[nextIndex]
    const before = next[nextIndex + 1]?.key ?? null

    if (newIndexToOldIndexMap[middleIndex] === 0) {
      operations.push({ kind: 'mount', key: nextChild.key, before })
    } else if (moved) {
      if (lisCursor < 0 || middleIndex !== lisIndices[lisCursor]) {
        operations.push({ kind: 'move', key: nextChild.key, before })
      } else {
        lisCursor -= 1
      }
    }
  }

  return { operations, newIndexToOldIndexMap, lisIndices }
}
```

与真实 Vue 的差异：

- 没有 unkeyed matching、VNode normalize、Fragment、Teleport、Suspense；
- 没有真正调用 `patch`，也不处理 host anchor；
- type 改变时教学实现显式 unmount+mount，真实 `patch` 自己处理不同 type；
- 没有 optimized/block fast path；
- 操作列表用于解释，不是可用 renderer。

### 4. 核心单元测试

```ts
import { describe, expect, it } from 'vitest'
import { getSequence, traceKeyedDiff } from './traceKeyedDiff'

const row = (key: string, type = 'Row') => ({ key, type })

describe('traceKeyedDiff', () => {
  it('traces the unknown middle', () => {
    const trace = traceKeyedDiff(
      ['A', 'B', 'C', 'D', 'E'].map(key => row(key)),
      ['A', 'C', 'B', 'F', 'E'].map(key => row(key)),
    )

    expect(trace.newIndexToOldIndexMap).toEqual([3, 2, 0])
    expect(trace.lisIndices).toEqual([1])
    expect(trace.operations).toContainEqual({ kind: 'unmount', key: 'D' })
    expect(trace.operations).toContainEqual({
      kind: 'mount',
      key: 'F',
      before: 'E',
    })
    expect(trace.operations).toContainEqual({
      kind: 'move',
      key: 'C',
      before: 'B',
    })
  })

  it('rejects duplicate keys', () => {
    expect(() => traceKeyedDiff([row('A'), row('A')], [])).toThrow(
      'duplicate key: A',
    )
  })

  it('treats equal key with changed type as replacement', () => {
    const trace = traceKeyedDiff([row('A', 'Old')], [row('A', 'New')])
    expect(trace.operations).toEqual([
      { kind: 'unmount', key: 'A' },
      { kind: 'mount', key: 'A', before: null },
    ])
  })

  it('ignores zero in LIS', () => {
    expect(getSequence([3, 2, 0])).toEqual([1])
  })
})
```

随机 oracle 不应断言“move 次数等于某个手写算法”的全部内部细节。它至少应把 operations 应用到一个 key 数组模型，并证明最终顺序、唯一性与输入不变；对小规模可穷举最长递增子序列长度，验证 move 下界。

### 5. Vue 集成测试的关键断言

`EditableRow`：

```vue
<script setup lang="ts">
import { getCurrentInstance, onMounted, ref } from 'vue'

defineProps<{ ticket: { id: string } }>()
const draft = ref('')
const uid = getCurrentInstance()?.uid
const mountedCount = ref(0)
onMounted(() => { mountedCount.value += 1 })
</script>

<template>
  <label :data-ticket-id="ticket.id" :data-uid="uid">
    {{ ticket.id }}
    <input v-model="draft" />
    <output data-mounted>{{ mountedCount }}</output>
  </label>
</template>
```

测试流程：

1. mount A～E；
2. 在 B 输入 `draft-B`，C 输入 `draft-C`；
3. 保存 B、C 的 `data-uid`；
4. 更新为 A、C、B、F、E；
5. `await nextTick()`；
6. 按 `data-ticket-id` 查找，而不是按 DOM index；
7. 断言 B/C draft 与 uid 未变，mounted count 仍为 1；
8. D 不存在，F mounted count 为 1。

若改用 index key，DOM 位置 1 的旧 B 实例会被当作新 C，位置 2 的旧 C 会被当作新 B。本地 draft 因此跟位置走。这正是事故证据。

### 6. 生产结论

修复 key 后还应：

- 数据入口拒绝重复 ID；
- 监控列表数据错误，而不是只依赖 Vue dev warning；
- 对插入、删除、排序保留组件状态写回归测试；
- 如果草稿的生命周期应超越列表项，提升到以 ticket id 索引的专用 draft store；
- 大列表使用虚拟化和分页，不能因为 diff 是线性/`n log n` 就渲染全部。

---

## 练习 2 参考答案：Scheduler Timeline 与陈旧 DOM 生产事故

### 1. 先给“部分顺序”，不要编造过度精确的全序

对于题目中 `choose('B')`：

```text
selected 写入
  → Vue flush microtask 被注册
sync 日志：旧 DOM A
  → external Promise microtask 被注册
  → await nextTick 订阅 currentFlushPromise

Vue flush：
  pre watcher：旧 DOM A
  component update：DOM 变 B
  post watcher / updated：新 DOM B（两者都属于 post；不要依赖无文档保证的细粒度互序）

之后：
  external-promise（本例在 nextTick continuation 之前已经入队）
  tick：新 DOM B
```

稳定可断言的偏序：

```text
sync < pre < DOM patch < {post, updated} < nextTick continuation
```

外部 Promise 若在 `selected.value = value` **之前**注册，它会先于 Vue flush；若之后注册，则 Vue flush 已先进入微任务队列。不要把这个实验结果上升为“所有 Promise 永远在 Vue 前/后”。

### 2. 可控 timeline helper

题目原接口把 `trigger` 允许为 async，容易让调用方在 helper 取同步快照前就等待。更清晰的接口：

```ts
import { nextTick } from 'vue'

export interface PhaseSnapshot {
  afterSync: readonly string[]
  afterNextTick: readonly string[]
  afterExtraMicrotask: readonly string[]
}

export async function captureTimeline(
  triggerSync: () => void,
  readEvents: () => readonly string[],
): Promise<PhaseSnapshot> {
  triggerSync()
  const afterSync = [...readEvents()]

  await nextTick()
  const afterNextTick = [...readEvents()]

  await Promise.resolve()
  const afterExtraMicrotask = [...readEvents()]

  return { afterSync, afterNextTick, afterExtraMicrotask }
}
```

命名为 `afterNextTick`，而不是虚构一个可以从 public API 精确暂停的“Vue flush 结束但任何其他微任务都没跑”瞬间。若要研究 scheduler 内部每一阶段，应在固定源码 fork 的测试中插 probe；业务测试应断言可观察语义。

### 3. 一个避免顺序脆弱的测试

```ts
import { mount } from '@vue/test-utils'
import { expect, it } from 'vitest'
import TimelineFixture from './TimelineFixture.vue'

function indexOfPrefix(events: readonly string[], prefix: string): number {
  return events.findIndex(event => event.startsWith(prefix))
}

it('commits DOM between pre and post phases', async () => {
  const wrapper = mount(TimelineFixture, { attachTo: document.body })

  const pending = wrapper.vm.choose('B')
  expect(wrapper.vm.events).toContain('sync:A')

  await pending
  const events = wrapper.vm.events as string[]

  expect(events).toContain('pre:A')
  expect(events).toContain('post:B')
  expect(events).toContain('updated')
  expect(events).toContain('tick:B')

  expect(indexOfPrefix(events, 'sync:')).toBeLessThan(
    indexOfPrefix(events, 'pre:'),
  )
  expect(indexOfPrefix(events, 'pre:')).toBeLessThan(
    indexOfPrefix(events, 'post:'),
  )
  expect(indexOfPrefix(events, 'post:')).toBeLessThan(
    indexOfPrefix(events, 'tick:'),
  )

  wrapper.unmount()
})
```

不要无根据断言 post watcher 一定在 `onUpdated` 前或后。若业务真的需要二者严格协调，应把它们合并到同一个公开控制点，而不是依赖内部 id 排序。

### 4. 父子与同栈三次写入

```ts
function chooseFinal(): void {
  selected.value = 'B'
  selected.value = 'C'
  selected.value = 'D'
}
```

父组件 render effect 在第一次失效时入队，后两次看到同一个 job 已 `QUEUED`。父 render 读取最终 D，传给子组件；子是否独立排 job、是否由父 patch 同步触发更新，要结合具体更新路径，但最终不能为每个中间值都做完整 DOM patch。

推荐测试记录的是：

```ts
const parentRenders = ref(0)
const childRenders = ref(0)

// fixture render 中或 onRenderTriggered 开发探针记录
```

断言本轮最终值与 render 次数上界，不要把内部 `flushIndex` 暴露给业务。

父先于子是 scheduler 依靠 uid/job id 维护的重要内部不变量：父创建早、uid 小；父若在更新中卸载子，disposed child job 可被跳过。升级时保护“不会在卸载后提交子 DOM/副作用”这一公开结果，而不是锁死 uid 数值。

### 5. 递归环与错误修复

错误图：

```text
watch reads selected=A
  → callback writes B
  → watcher job 再次运行，reads B
  → callback writes A
  → 永不收敛
```

错误“修复”：

```ts
let count = 0
watch(selected, value => {
  if (count++ < 99) selected.value = value === 'A' ? 'B' : 'A'
})
```

这只是把无限环变成 99 次无意义更新，而且绑定了内部上限。

正确方案取决于业务。若需求是把非法选择规范化，只在值不合法时单向写入 canonical value：

```ts
const allowed = new Set(['A', 'B'] as const)
type Selection = 'A' | 'B'

function normalizeSelection(input: string): Selection {
  return allowed.has(input as Selection) ? (input as Selection) : 'A'
}

function choose(input: string): void {
  const normalized = normalizeSelection(input)
  if (selected.value !== normalized) {
    selected.value = normalized
  }
}
```

若 A/B 是业务状态机：

```ts
type State =
  | { tag: 'idle'; selected: string | null }
  | { tag: 'loading'; selected: string; requestId: string }
  | { tag: 'ready'; selected: string }
  | { tag: 'failed'; selected: string; message: string }

type Event =
  | { type: 'select'; id: string }
  | { type: 'resolved'; id: string; requestId: string }
  | { type: 'rejected'; id: string; requestId: string; message: string }
```

由 reducer 决定合法迁移，watcher 只执行副作用并通过带 requestId 的事件回传，不直接来回翻转同一 source。

测试需证明：

- 一个用户 `select` 最终进入唯一稳定状态；
- stale response 不回写；
- unmount 时停止 watcher/abort 请求；
- 多次选择后没有 recursive update warning；
- 测试不靠 100 次上限。

### 6. 源码证据链

固定链接：

- [`renderer.ts#setupRenderEffect`](https://github.com/vuejs/core/blob/v3.5.42/packages/runtime-core/src/renderer.ts)：创建 `ReactiveEffect(componentUpdateFn)`，把 scheduler 指向 `queueJob(job)`；
- [`scheduler.ts`](https://github.com/vuejs/core/blob/v3.5.42/packages/runtime-core/src/scheduler.ts)：`queueJob` 以 flag 去重，以 id 排序；
- 同文件 `flushPreFlushCbs`：抽取 PRE job；
- 同文件 `flushPostFlushCbs`：去重、排序、执行 post callbacks；
- 同文件 `flushJobs`：try/finally 清理 flags、flush post，并继续 drain 新任务；
- 同文件 `nextTick`：使用 `currentFlushPromise || resolvedPromise`。

公开可依赖的语义：Vue 会批处理 DOM 更新，`nextTick` 可等待当前 DOM update flush，watch 支持 documented flush timing。

当前内部实现：Promise 微任务、uid 排序、bit flags、递归计数和具体队列数组。生产代码不能导入或 monkey patch 它们。

### 7. 常见错误与最小反例

| 错误 | 最小反例 | 正确方向 |
| --- | --- | --- |
| 写状态后同步读 DOM | `x.value++; el.textContent` | post/nextTick |
| 把 nextTick 当 paint | tick 后立即截 layout-sensitive 动画首帧 | 明确是否需 rAF |
| 到处 sync watcher | 循环 push 1,000 项触发 1,000 回调 | 保留批处理，缩小同步桥接 |
| watcher 启请求不 cleanup | A 慢响应覆盖 B | AbortController/version |
| updated 中无条件写 render 依赖 | 每次 patch 再触发 patch | 单向状态机/比较后写 |
| 测试真实 sleep | CI 偶发超时 | deferred Promise/fake clock/nextTick |

### 8. 生产边界

Vue scheduler 是单个应用运行时内的 UI 调度机制，不是：

- 服务端任务队列；
- 跨 tab 一致性协议；
- 网络请求 singleflight；
- 浏览器帧调度器；
- 业务事件审计日志。

能解释这条边界，才算真正理解 scheduler，而不是把“Vue 会批处理”泛化成所有工作都会自动去重。
