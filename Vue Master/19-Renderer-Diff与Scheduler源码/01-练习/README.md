# 第 19 章练习：把 Diff 与调度变成可验证证据

> 本章恰好两题。第一题训练 renderer 身份与移动计划；第二题训练调度阶段、DOM 时序和递归故障。不得只给结论截图，必须提交可复现 fixture、断言和源码坐标。

## 练习 1：Keyed 列表状态保持与最小移动审计

### 场景

客服工作台显示可编辑工单行。每行组件内部保存一个尚未提交的 `draftNote`，列表会被服务端事件插入、删除和重排。线上曾发生“草稿跑到另一张工单”和“重排后所有行都重新 mounted”。

初始与目标顺序：

```text
old: A B C D E
new: A C B F E
```

### 任务 A：手工执行固定版本算法

以 Vue Core `v3.5.42` 的 `patchKeyedChildren` 为准，提交一张逐步表，必须包含：

1. 头部、尾部同步后的 `s1/e1/s2/e2`；
2. `keyToNewIndexMap`；
3. 遍历 B、C、D 后每一步的 `newIndexToOldIndexMap`；
4. `patched`、`maxNewIndexSoFar`、`moved`；
5. LIS 返回的**新中段索引**；
6. 从右向左处理时每一步的 anchor；
7. A～F 分别发生 patch、mount、move、unmount 中的哪些动作。

### 任务 B：实现教学 tracer

实现：

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

export function traceKeyedDiff(
  previous: readonly Child[],
  next: readonly Child[],
): DiffTrace
```

约束：

- 不得调用 Vue 私有函数；你实现的是固定算法的教学模型；
- 先验证同一列表内 key 唯一，重复时抛出带 key 的错误；
- type+key 才表示相同身份；同 key 不同 type 应卸载再挂载；
- 输入不可变；
- `before` 表示目标右邻 key，没有右邻时为 `null`；
- 实现 `getSequence` 或等价 `O(n log n)` LIS，0 不参加；
- tracer 不必模拟 Element/Fragment/Teleport，只服务本题边界。

### 任务 C：Vue 集成证据

再写一个最小 Vue fixture：

```vue
<EditableRow
  v-for="ticket in tickets"
  :key="ticket.id"
  :ticket="ticket"
/>
```

每行显示 instance uid 或自增 mount token，并有内部 draft input。使用 Vue Test Utils 或 Playwright 证明：

- 从 old 变到 new 后，B/C/E 的内部草稿跟随业务 ID；
- D 被卸载；F 新挂载；
- B/C 的 mounted hook 没有再次运行；
- 把 key 故意改成 index 后，至少一个断言失败，并解释为何失败。

### 最少测试矩阵

- 空 → 空；空 → 三项；三项 → 空；
- 尾部追加、头部插入、reverse、局部 swap；
- 同 key 同 type；同 key不同 type；
- 重复 key 拒绝；
- old/new 输入在调用后未改变；
- 1,000 项固定 seed shuffle，结果顺序正确。

### 发散问题

1. 如果 key 是服务端临时 ID，保存成功后换成数据库 ID，如何避免整行 remount？
2. Fragment 或 TransitionGroup 会给 move/anchor 增加哪些约束？
3. 10 万行列表即使 diff 正确，为什么仍应虚拟化？
4. 若业务必须保留离开列表的草稿，应由 key、KeepAlive 还是外部状态解决？

### 交付物

- 状态表与源码固定链接；
- `traceKeyedDiff.ts`；
- 单元测试与 Vue 集成测试；
- 一页事故复盘：错误身份、触发条件、监测方法、修复和回归项。

---

## 练习 2：Scheduler Timeline 与陈旧 DOM 生产事故

### 场景

一个父组件控制筛选条件，子组件渲染选中行。代码同时使用默认 watcher、post watcher、`onUpdated`、`nextTick` 和一个外部 Promise。开发者不能解释日志顺序，还用 `flush: 'sync'` 修过一次，最终制造了递归更新。

### 起始 fixture

```vue
<script setup lang="ts">
import { nextTick, onUpdated, ref, watch } from 'vue'

const selected = ref('A')
const events: string[] = []

watch(selected, () => {
  events.push(`pre:${document.querySelector('[data-selected]')?.textContent}`)
})

watch(
  selected,
  () => {
    events.push(`post:${document.querySelector('[data-selected]')?.textContent}`)
  },
  { flush: 'post' },
)

onUpdated(() => events.push('updated'))

async function choose(value: string) {
  selected.value = value
  events.push(`sync:${document.querySelector('[data-selected]')?.textContent}`)
  Promise.resolve().then(() => events.push('external-promise'))
  await nextTick()
  events.push(`tick:${document.querySelector('[data-selected]')?.textContent}`)
}
</script>

<template>
  <p data-selected>{{ selected }}</p>
</template>
```

### 任务 A：写 phase oracle

实现一个测试辅助器，而不是 sleep：

```ts
export interface PhaseSnapshot {
  afterSync: readonly string[]
  afterVueFlush: readonly string[]
  afterMicrotasks: readonly string[]
}

export async function captureTimeline(
  trigger: () => void | Promise<void>,
  readEvents: () => readonly string[],
): Promise<PhaseSnapshot>
```

你可以调整接口以避免 `trigger()` 自己等待 `nextTick` 导致阶段不可分，但必须在 README 说明控制点。测试需明确：

- 同步阶段看旧 DOM；
- pre 在组件 patch 前；
- post 与 updated 在 DOM commit 后；
- `nextTick` continuation 在当前 Vue flush 完成后；
- 外部 Promise 的顺序由注册时机决定，至少写两组改变注册顺序的用例。

### 任务 B：父子更新和 job 去重

增加 Parent/Child：父把 `selected` 作为 prop 传给子，二者都记录 render、pre/post/updated。一次同步调用中连续写入 B、C、D。

断言并解释：

- DOM 最终只显示 D；
- 组件 update job 被批处理，而不是为每个中间值各 patch 一次；
- 父子相对顺序与 uid/job id 的关系；
- watcher 是否看见所有中间值取决于 flush 策略与写入边界，不能用组件 job 去重替代业务事件审计。

### 任务 C：制造并修复递归更新

构造一个只在测试环境运行的最小环：

```ts
watch(selected, value => {
  selected.value = value === 'A' ? 'B' : 'A'
})
```

要求：

1. 捕获 Vue 开发模式递归更新错误或警告；
2. 画出 read/write 环；
3. 用显式状态机或单向事件修复，不能靠计数小于 100；
4. 写回归测试证明一次用户事件最终收敛；
5. 清理所有 watcher，测试间无泄漏。

### 任务 D：源码说明

报告中固定链接并解释：

- `setupRenderEffect` 怎样创建 effect/job；
- `queueJob` 怎样去重和插入；
- `flushPreFlushCbs` / `flushPostFlushCbs`；
- `flushJobs` 的 finally 为什么必须清 flag 并继续 drain；
- `nextTick` 为什么等待 `currentFlushPromise`。

### 最少测试矩阵

- 一次写入、同栈三次写入、两个不同 macrotask 写入；
- 父更新时子仍存在、父更新时子被卸载；
- pre/post/sync watcher；
- watcher callback 抛错后，后续更新仍能入队；
- 组件卸载后无延迟 DOM 写入；
- fake timers 只用于你自己的 timer；Vue microtask 用明确 Promise/flush helper 推进。

### 发散问题

1. `nextTick` 后再 `requestAnimationFrame` 比只用 `nextTick` 多等待什么？
2. Router 导航完成、组件 DOM commit、浏览器 paint 是同一个时间点吗？
3. 若 post watcher 启动网络请求，连续变化时如何取消旧请求？
4. 服务端渲染没有浏览器 DOM，这套 phase 模型哪些部分仍成立？

### 交付物

- 可运行 Parent/Child fixture；
- timeline helper 与确定性测试；
- 递归更新最小复现和修复；
- 一份 500～1,000 字技术说明，区分公开语义与 v3.5.42 内部实现。
