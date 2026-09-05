# 第 17 章答案：用固定源码证明，而不是凭印象解释

> 本答案只对应 [`vuejs/core@v3.5.42`](https://github.com/vuejs/core/releases/tag/v3.5.42)，发布提交 `d63616c`。内部 version 数字和链表形态不是公共 API。

## 题 1 参考答案：条件依赖的真实 Link 生命周期

### 1. 先验证 checkout

```bash
git clone https://github.com/vuejs/core.git vue-core-3.5.42
cd vue-core-3.5.42
git checkout v3.5.42
git rev-parse --short HEAD
git status --short
```

预期 short commit 为 `d63616c`，工作区为空。实验使用仓库要求的 pnpm/Node 版本；安装时使用 frozen lockfile。不要把本答案中的未来工具版本写死成你的环境事实。

固定证据：

- [`dep.ts`](https://github.com/vuejs/core/blob/v3.5.42/packages/reactivity/src/dep.ts)
- [`effect.ts`](https://github.com/vuejs/core/blob/v3.5.42/packages/reactivity/src/effect.ts)
- [`computed.ts`](https://github.com/vuejs/core/blob/v3.5.42/packages/reactivity/src/computed.ts)
- [`baseHandlers.ts`](https://github.com/vuejs/core/blob/v3.5.42/packages/reactivity/src/baseHandlers.ts)
- [`effect.spec.ts`](https://github.com/vuejs/core/blob/v3.5.42/packages/reactivity/__tests__/effect.spec.ts)
- [`computed.spec.ts`](https://github.com/vuejs/core/blob/v3.5.42/packages/reactivity/__tests__/computed.spec.ts)

### 2. 给实体命名

后文使用：

```text
E   outer ReactiveEffect
C   ComputedRefImpl(selected)

DU  Dep(rawState, 'useA')
DA  Dep(rawState, 'a')
DB  Dep(rawState, 'b')
DC  selected.dep（computed 面向消费者的 Dep）

LEC Link(E <-> DC)
LCU Link(C <-> DU)
LCA Link(C <-> DA)
LCB Link(C <-> DB)
```

初始 `globalVersion = 0` 的前提是这段程序在一个新加载的 reactivity 模块中运行，且此前没有其他 trigger。若放进共享 test process，绝对值可能不同；应断言增量和关系，而非硬编码全局起点。

### 3. 首次 `effect()` 完成

调用链：

```text
effect(outerFn)
  -> new ReactiveEffect(outerFn) = E
  -> E.run()
     -> prepareDeps(E)，首次为空
     -> activeSub = E
     -> outerFn reads selected.value
        -> DC.track(E)
           -> 新建 LEC，初始 link.version = DC.version = 0
           -> E.deps += LEC
           -> DC.subs += LEC
           -> 因 DC.computed=C 且它获得首个 subscriber：
              C flags 加 TRACKING|DIRTY
        -> refreshComputed(C)
           -> C.globalVersion(-1) != globalVersion(0)
           -> activeSub = C
           -> getter reads state.useA
              -> base get -> track raw/useA -> 新建 DU -> 新建 LCU
           -> getter reads state.a
              -> 新建 DA -> 新建 LCA
           -> result undefined -> 1
           -> DC.version 0 -> 1
        -> LEC.version 同步成 DC.version = 1
     -> output = 1
     -> cleanupDeps(E)
```

状态表：

| 项 | 首次完成后 |
|---|---|
| output | `1` |
| globalVersion | 未发生 mutation，仍是起点 |
| DU.version | `0` |
| DA.version | `0` |
| DB | 尚未创建 |
| DC.version | `1`，首次 computed 结果建立 |
| E.deps | `LEC(DC, link.version=1)` |
| C.deps | `LCU(DU, 0) -> LCA(DA, 0)` |
| DC.subs | `E` |
| DU.subs | `C` |
| DA.subs | `C` |
| C flags | `TRACKING + EVALUATED`，运行结束后不 DIRTY |

outer effect 不直接读 `state.useA/a`，所以不会直接出现在 DU/DA 的 subs 链。C 才是这些 property Deps 的 subscriber。

### 4. 第一次 `state.a = 2`

#### 4.1 set/trigger

```text
MutableReactiveHandler.set(rawState, 'a', 2)
  oldValue = 1
  hadKey = true
  Reflect.set succeeds
  hasChanged(2, 1) = true
  trigger(rawState, SET, 'a', 2, 1)
```

`trigger()` 找 DA，进入 batch。`DA.trigger()`：

```text
DA.version 0 -> 1
globalVersion + 1
DA.notify()
  -> C.notify()
     -> C DIRTY
     -> batch(C, isComputed=true)
     -> return true
  -> DC.notify()
     -> E.notify()
     -> batch(E)
```

注意 `DC.notify()` 不是 `DC.trigger()`，此刻不直接增加 DC.version。只有 computed 实际刷新且输出变化，DC.version 才增加。

#### 4.2 outer effect 的 dirty check 触发 computed refresh

最外层 batch 结束，E 被触发：

```text
E.runIfDirty()
  -> isDirty(E)
     LEC: DC.version(1) == LEC.version(1)
     但 DC.computed 存在 -> refreshComputed(C)
```

C 刷新：

1. 清 DIRTY；
2. 发现 globalVersion 变化；
3. `isDirty(C)` 发现 `DA.version(1) != LCA.version(0)`；
4. `prepareDeps(C)` 把 LCU/LCA.version 设 -1；
5. getter 依次读 useA、a；
6. 两个 Link 被复用并同步版本；
7. 新结果 2 与旧结果 1 不同；
8. `DC.version 1 -> 2`；
9. cleanup 后 C.deps 仍按 `DU -> DA`；
10. E 看到 DC.version 与 LEC.version 不同，因此真的 `E.run()`；
11. E 再读 selected，computed 已干净，LEC.version 同步到 2；
12. `output = 2`。

状态：

| 项 | 结果 |
|---|---|
| DA.version | `1` |
| LCA.version | `1` |
| globalVersion | 相对首次 `+1` |
| DC.version | `2` |
| LEC.version | `2` |
| computed getter | 比首次多执行 1 次 |
| outer effect | 比首次多执行 1 次 |

### 5. 第二次 `state.a = 2`

base handler 的 `hasChanged(newValue, oldValue)` 为 false：

- 不调用 `trigger()`；
- DA.version 不变；
- globalVersion 不变；
- C 不 DIRTY；
- getter 不执行；
- E 不执行；
- output 仍为 2。

如果你的插桩显示触发，先查测试是否在 setter 之外还写了其他 reactive state，或是否比较的是不同 raw/proxy 对象。

### 6. `state.useA = false`：分支切换

DU.version 递增，globalVersion 再加 1，C/E 进入同样的通知链。真正变化在 C.run：

#### 6.1 prepare

```text
C.deps before: LCU -> LCA

prepareDeps(C):
  LCU.version = -1; DU.activeLink = LCU
  LCA.version = -1; DA.activeLink = LCA
```

#### 6.2 getter

先读 `useA`：

- `Dep.track()` 找到属于 C 的 LCU；
- LCU.version 从 -1 同步为 DU.version；
- Link 被调整到当前读取顺序的 tail。

条件为 false，不读 a；接着读 b：

- depsMap 中无 DB，创建 DB；
- 创建 LCB；
- 追加到 C.deps 与 DB.subs。

#### 6.3 cleanup

LCA.version 仍为 -1：

- `removeSub(LCA)` 从 DA 的 subs 双链摘除；
- `removeDep(LCA)` 从 C 的 deps 双链摘除；
- 若 DA.sc 归零，从 rawState 的 depsMap 删除 key `a`；
- C.deps 成为 `LCU -> LCB`。

computed 新结果从 2 变 10，所以：

```text
DC.version 2 -> 3
LEC 最终同步 3
output = 10
```

状态表：

| 项 | 分支切换后 |
|---|---|
| output | `10` |
| C.deps | `DU -> DB` |
| DU.subs | C |
| DB.subs | C |
| DA.subs | 空 |
| `getDepFromReactive(raw, 'a')` | 若无其他 subscriber，应为 `undefined` |
| DC.version | `3` |
| globalVersion | 相对首次 `+2` |

### 7. `state.a = 3`

这是最容易写错的一步。

分支切换后 DA 已可能从 depsMap 删除。raw 值仍会成功变成 3，但没有 key `a` 的 Dep 需要通知：

- C 不被 notify；
- E 不被 notify；
- output 仍 10；
- computed getter 不执行。

在 v3.5.42 的精确实现中，若这个 target 的 depsMap 仍存在，而 key `a` 的 Dep 不存在且没有相关 iteration Dep 被选中，则没有 `Dep.trigger()`，因此 globalVersion 也不会因这次写入推进。`trigger()` 只有在整个 depsMap 不存在时才有一个直接推进 globalVersion 的早退分支。

这个细节是内部实现事实，测试应以固定 tag 验证；业务不能依赖“未被追踪的写是否改变 globalVersion”。

### 8. `state.b = 11`

DB 存在且订阅 C：

```text
DB.version 0 -> 1
globalVersion + 1
C DIRTY
C refresh: 10 -> 11
DC.version 3 -> 4
E run
LEC.version -> 4
output = 11
```

C.deps 仍是 DU -> DB。

### 9. `stop(runner)` 与之后的 `state.b = 12`

`E.stop()`：

1. 沿 E.deps 移除 LEC；
2. E.deps/depsTail 清空；
3. cleanup/onStop；
4. E 清 ACTIVE。

LEC 是 DC 的最后一个 subscriber 时，`removeSub` 发现 DC 属于 computed：

- C 清 TRACKING；
- C 从 DU/DB 的 subs 链 soft unsubscribe；
- C 自己仍保留 deps Links，用于后续惰性检查；
- source Dep 的 `sc` 不按普通移除减少，因为 computed 仍引用这些 deps。

然后 `state.b = 12`：

- raw b 更新；
- DB.version 继续增加；
- globalVersion 增加；
- DB.subs 已无 C，所以不标 C DIRTY、不运行 E；
- output 仍为 11。

如果此后手工读取 `selected.value`，C 会因 globalVersion/DB version 差异惰性刷新为 12；但题目没有这次读取。

### 10. 完整结果时间线

假设独立模块、初始 globalVersion 为 0：

| 操作 | output | globalVersion | DU.v | DA.v/是否仍映射 | DB.v | DC.v | getter 次数 | E 次数 |
|---|---:|---:|---:|---|---:|---:|---:|---:|
| 初次 effect | 1 | 0 | 0 | 0 / 是 | 不存在 | 1 | 1 | 1 |
| a=2 | 2 | 1 | 0 | 1 / 是 | 不存在 | 2 | 2 | 2 |
| a=2 again | 2 | 1 | 0 | 1 / 是 | 不存在 | 2 | 2 | 2 |
| useA=false | 10 | 2 | 1 | 旧 DA / 从 map 删除 | 0 | 3 | 3 | 3 |
| a=3 | 10 | 2 | 1 | 无当前 Dep | 0 | 3 | 3 | 3 |
| b=11 | 11 | 3 | 1 | 无当前 Dep | 1 | 4 | 4 | 4 |
| stop | 11 | 3 | 1 | 无当前 Dep | 1 | 4 | 4 | 4 |
| b=12 | 11 | 4 | 1 | 无当前 Dep | 2 | 4 | 4 | 4 |

不要在共享测试进程断言 globalVersion 绝对为这些值。断言 mutation 前后 delta，并说明无 Dep 的 `a=3` 特例。

### 11. Test-only inspection helper

下面代码应放在临时 spec，不进入 src/index exports：

```ts
import type { ComputedRefImpl } from '../src/computed'
import { type Dep, type Link, getDepFromReactive } from '../src/dep'
import type { Subscriber } from '../src/effect'
import { computed, effect, reactive, stop, toRaw } from '../src'
import { describe, expect, it, vi } from 'vitest'

const depNames = new WeakMap<object, string>()
const subNames = new WeakMap<object, string>()
const MAX_LINKS = 100

function nameDep(dep: Dep, name: string) {
  depNames.set(dep, name)
  return dep
}

function nameSub(sub: Subscriber, name: string) {
  subNames.set(sub, name)
  return sub
}

interface LinkSnapshot {
  depName: string
  depVersion: number
  linkVersion: number
}

function linksOfSub(sub: Subscriber): Link[] {
  const result: Link[] = []
  let previous: Link | undefined
  let link = sub.deps

  while (link) {
    if (result.length >= MAX_LINKS) throw new Error('cycle or oversized dep list')
    expect(link.prevDep).toBe(previous)
    if (previous) expect(previous.nextDep).toBe(link)
    result.push(link)
    previous = link
    link = link.nextDep
  }

  expect(previous).toBe(sub.depsTail)
  return result
}

function linksOfDep(dep: Dep): Link[] {
  const reversed: Link[] = []
  let next: Link | undefined
  let link = dep.subs

  while (link) {
    if (reversed.length >= MAX_LINKS) throw new Error('cycle or oversized sub list')
    expect(link.nextSub).toBe(next)
    if (next) expect(next.prevSub).toBe(link)
    reversed.push(link)
    next = link
    link = link.prevSub
  }

  return reversed.reverse()
}

function snapshotSubscriber(sub: Subscriber): LinkSnapshot[] {
  return linksOfSub(sub).map(link => ({
    depName: depNames.get(link.dep) ?? 'unnamed-dep',
    depVersion: link.dep.version,
    linkVersion: link.version,
  }))
}

function snapshotDep(dep: Dep): string[] {
  return linksOfDep(dep).map(link => subNames.get(link.sub) ?? 'unnamed-sub')
}

function assertBidirectionalIntegrity(
  subscribers: Subscriber[],
  deps: Dep[],
) {
  const fromSubscribers = new Set(subscribers.flatMap(linksOfSub))
  const fromDeps = new Set(deps.flatMap(linksOfDep))
  expect(fromSubscribers).toEqual(fromDeps)

  for (const link of fromSubscribers) {
    expect(link.sub).toBeDefined()
    expect(link.dep).toBeDefined()
  }
}
```

当某 Dep 被从 targetMap 删除后，旧 Dep 对象仍可能被测试变量引用。此时“双向完整性”应只对当前活跃图或你明确收集的 detached old node 分别断言，不能把已删除 link 误加入 current graph。

### 12. 核心 spec

```ts
it('tracks and cleans conditional deps using real Link lists', () => {
  const computedSpy = vi.fn()
  const effectSpy = vi.fn()
  const state = reactive({ useA: true, a: 1, b: 10 })
  const raw = toRaw(state)
  const selected = computed(() => {
    computedSpy()
    return state.useA ? state.a : state.b
  }) as unknown as ComputedRefImpl<number>

  let output = -1
  const runner = effect(() => {
    effectSpy()
    output = selected.value
  })

  const outer = nameSub(runner.effect, 'outer')
  nameSub(selected, 'computed')
  const dc = nameDep(selected.dep, 'selected')
  const du = nameDep(getDepFromReactive(raw, 'useA')!, 'useA')
  const da = nameDep(getDepFromReactive(raw, 'a')!, 'a')

  expect(output).toBe(1)
  expect(snapshotSubscriber(outer)).toEqual([
    { depName: 'selected', depVersion: 1, linkVersion: 1 },
  ])
  expect(snapshotSubscriber(selected).map(x => x.depName)).toEqual(['useA', 'a'])
  expect(snapshotDep(dc)).toEqual(['outer'])
  expect(snapshotDep(du)).toEqual(['computed'])
  expect(snapshotDep(da)).toEqual(['computed'])

  state.a = 2
  expect(output).toBe(2)
  expect(computedSpy).toHaveBeenCalledTimes(2)
  expect(effectSpy).toHaveBeenCalledTimes(2)

  state.a = 2
  expect(computedSpy).toHaveBeenCalledTimes(2)
  expect(effectSpy).toHaveBeenCalledTimes(2)

  state.useA = false
  const db = nameDep(getDepFromReactive(raw, 'b')!, 'b')
  expect(output).toBe(10)
  expect(snapshotSubscriber(selected).map(x => x.depName)).toEqual(['useA', 'b'])
  expect(getDepFromReactive(raw, 'a')).toBeUndefined()
  expect(snapshotDep(da)).toEqual([])
  expect(snapshotDep(db)).toEqual(['computed'])

  state.a = 3
  expect(computedSpy).toHaveBeenCalledTimes(3)
  expect(effectSpy).toHaveBeenCalledTimes(3)

  state.b = 11
  expect(output).toBe(11)
  expect(computedSpy).toHaveBeenCalledTimes(4)
  expect(effectSpy).toHaveBeenCalledTimes(4)

  assertBidirectionalIntegrity([outer, selected], [dc, du, db])

  stop(runner)
  expect(snapshotDep(dc)).toEqual([])
  expect(snapshotSubscriber(outer)).toEqual([])

  state.b = 12
  expect(output).toBe(11)
  expect(computedSpy).toHaveBeenCalledTimes(4)
  expect(effectSpy).toHaveBeenCalledTimes(4)
})
```

注意：固定 tag 的 `getDepFromReactive` 位于内部 `dep.ts`，不从业务主包公开。这个 spec 在源码仓库中使用它是为了学习，不代表应用可以 import。

### 13. 访问顺序发散题

旧 deps：`useA -> a -> x`；新访问：`x -> useA -> b`：

- `x` Link 复用，并移动到当前 deps tail；
- `useA` Link 复用，再移动到 tail；
- `b` 新建并追加；
- `a` 保持 -1，cleanup 时从两侧删除；
- 最终链：`x -> useA -> b`。

移动不是为了语义上的“优先级”，而是保证 deps 顺序反映最近实际读取，便于后续 prepare/cleanup 与 dirty 顺序检查。

### 14. 两个消费者

若 E1、E2 都读取 selected：

- DC.subs 有两个 Links，各指向一个 outer effect；
- C 仍只通过每个 source 一个 Link 订阅 DU/DA；
- DC.sc/订阅链反映两个消费者；
- stop E1 后 C 仍 TRACKING，因为 DC 还有 E2；
- stop 最后一个消费者后，C 才 soft unsubscribe sources。

多消费者不会复制 computed getter 或复制 C 的 source deps 链。

### 15. Benchmark 报告模板

```text
baseline tag/commit:
patch commit:
Node/pnpm/OS/CPU/power mode:
warmup:
runs:
benchmark cases:
median / p95 / variance:
memory/GC observation:
correctness commands:
instrumentation disabled: yes/no
```

插桩 spec 不应影响 src 热路径，因此无需为它声称性能结论。若改 src 加日志，先还原后再 benchmark。

---

## 题 2 参考答案：三个应用生命周期错误，不是 cleanupDeps 证据

### 1. 结论先行

| 现象 | 根因 | 责任层 |
|---|---|---|
| WebSocket count 不更新 | 回调写了 raw，绕过 Proxy.set/trigger | 应用边界错误 |
| T1 慢响应覆盖 T2 | watcher 没取消/世代校验 | 应用异步竞态 |
| 进入离开后多次 paint/request | detached scope 与 socket 无 dispose | 应用资源泄漏 |
| “条件 cleanup 坏了” | 当前证据不能支持；泄漏实例仍活着造成假象 | 错误归因 |

`cleanupDeps()` 只负责**同一个 Subscriber 重跑时**移除本轮未读取的 dependency Links。它不负责：

- 侦测 raw object 的直接写；
- 取消 Promise；
- 自动停止 detached scope；
- 关闭外部 socket；
- 销毁已经丢失 owner 的面板实例。

### 2. 第一症状：raw 写绕过 handler

原代码：

```ts
const state = reactive(rawModel)
const raw = toRaw(state)
raw.liveCount = message.value
```

赋值发生在普通对象上，没有进入 [`MutableReactiveHandler.set`](https://github.com/vuejs/core/blob/v3.5.42/packages/reactivity/src/baseHandlers.ts)，因此没有 `trigger()`，没有 onTrigger，没有 Dep.version 变化。

最小证明：

```ts
it('raw writes are not reactive; proxy writes are', () => {
  const raw = { count: 0 }
  const state = reactive(raw)
  const render = vi.fn(() => state.count)
  const runner = effect(render, { onTrigger: vi.fn() })

  expect(render).toHaveBeenCalledTimes(1)

  raw.count = 1
  expect(render).toHaveBeenCalledTimes(1)

  state.count = 2
  expect(render).toHaveBeenCalledTimes(2)

  stop(runner)
})
```

这不是“偶尔”不更新；对该依赖而言 raw 写就是不触发。线上看似偶尔，是因为其他 reactive mutation 之后重跑 effect，顺便读到了 raw 已改变的值。

### 3. 第二症状：watch cleanup 不等于自动存在

原 watcher 每次回调都创建一个无法协调的 Promise：

```text
t0 ticketId=T1 -> load(T1) slow
t1 ticketId=T2 -> load(T2) fast
t2 T2 resolve -> detail=T2
t3 T1 resolve -> detail=T1  // 错
```

Vue watch 提供 cleanup 生命周期，但应用必须注册。Abort 还只是资源优化：repository 可能忽略 signal，或服务端已完成。因此提交处需要 generation。

固定源码证据：

- [`watch.ts` cleanupMap/onWatcherCleanup`](https://github.com/vuejs/core/blob/v3.5.42/packages/reactivity/src/watch.ts)
- watch job 会在回调再次执行前调用旧 cleanup；
- stop effect 也调用 cleanup；
- Vue 不理解哪个 Promise 是“较新业务意图”。

### 4. 第三症状：detached scope 没有父 owner

`effectScope(true)` 明确 detached，不会因路由组件消失自动 stop。返回对象被丢弃不等于 effect 不可达：

```text
socket callback -> state proxy/raw
scope -> effects -> getter closures -> state/repository/detail
repository Promise -> callback -> detail
```

这些引用链足以让旧实例继续存活。每次 mount 再建一套，所以次数增长。

固定源码证据：

- [`EffectScope` constructor](https://github.com/vuejs/core/blob/v3.5.42/packages/reactivity/src/effectScope.ts) 只有非 detached scope 才挂 active parent；
- `stop()` 才会 stop effects、跑 cleanups、stop child scopes；
- 外部 socket 只有通过 `onScopeDispose` 或显式 dispose 才会关闭。

### 5. 条件依赖 cleanup 实际应怎样验证

只保留：

```ts
const state = reactive({ mode: 'live', liveCount: 0, archiveCount: 0 })
const paint = vi.fn()
const stop = watchEffect(() => {
  paint(state.mode === 'live' ? state.liveCount : state.archiveCount)
})

state.mode = 'archive'
const countAfterSwitch = paint.mock.calls.length
state.liveCount++
expect(paint).toHaveBeenCalledTimes(countAfterSwitch)
state.archiveCount++
expect(paint).toHaveBeenCalledTimes(countAfterSwitch + 1)
stop()
```

如果这在 v3.5.42 通过，条件 cleanup 主张没有复现。原应用多次 paint 更可能来自多个泄漏 Subscriber，而不是单 Subscriber 保留旧 Link。

### 6. 最小、完整的应用 patch

这里选择复制宿主输入，避免宿主持有 raw alias 后继续直接写。跨边界更新只能走 `apply()` 或内部 socket。

```ts
import {
  effectScope,
  onScopeDispose,
  readonly,
  reactive,
  shallowRef,
  watch,
  watchEffect,
  type Ref,
} from 'vue'

interface PanelModel {
  mode: 'live' | 'archive'
  liveCount: number
  archiveCount: number
  ticketId: string
}

interface Ticket {
  id: string
  title: string
}

interface Repository {
  load(id: string, options: { signal: AbortSignal }): Promise<Ticket>
}

interface SocketHandle {
  close(): void
}

type PanelMessage =
  | { type: 'live-count'; value: number }
  | { type: 'select-ticket'; id: string }

interface MountedPanel {
  state: PanelModel
  detail: Readonly<Ref<Ticket | null>>
  error: Readonly<Ref<unknown | null>>
  apply(patch: Partial<PanelModel>): void
  dispose(): void
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

export function mountPanel(
  initial: PanelModel,
  repository: Repository,
): MountedPanel {
  const state = reactive<PanelModel>({ ...initial })
  const detail = shallowRef<Ticket | null>(null)
  const error = shallowRef<unknown | null>(null)
  const scope = effectScope(true)
  let disposed = false
  let generation = 0

  scope.run(() => {
    watchEffect(() => {
      paintCount(
        state.mode === 'live' ? state.liveCount : state.archiveCount,
      )
    })

    watch(
      () => state.ticketId,
      async (id, _oldId, onCleanup) => {
        const mine = ++generation
        const controller = new AbortController()
        onCleanup(() => controller.abort('ticket changed or scope stopped'))
        error.value = null

        try {
          const ticket = await repository.load(id, {
            signal: controller.signal,
          })

          if (disposed || mine !== generation) return
          detail.value = ticket
        } catch (cause) {
          if (disposed || mine !== generation || isAbortError(cause)) return
          error.value = cause
        }
      },
      { immediate: true },
    )

    const socket: SocketHandle = connect((message: PanelMessage) => {
      if (disposed) return

      if (message.type === 'live-count') {
        state.liveCount = message.value
      } else {
        state.ticketId = message.id
      }
    })

    onScopeDispose(() => socket.close())
  })

  function apply(patch: Partial<PanelModel>) {
    if (disposed) return
    if (patch.mode !== undefined) state.mode = patch.mode
    if (patch.liveCount !== undefined) state.liveCount = patch.liveCount
    if (patch.archiveCount !== undefined) {
      state.archiveCount = patch.archiveCount
    }
    if (patch.ticketId !== undefined) state.ticketId = patch.ticketId
  }

  function dispose() {
    if (disposed) return
    disposed = true
    generation++
    scope.stop()
  }

  return {
    state,
    detail: readonly(detail),
    error: readonly(error),
    apply,
    dispose,
  }
}
```

### 7. 为什么这个 patch 足够小

它没有：

- 修改 Vue core；
- 读取 Dep/Link；
- 建新全局 store；
- 把所有请求改成复杂 query library；
- 对 raw 写后手工 `triggerRef()` 掩盖边界；
- 假设 abort 一定成功。

它只补上三个缺失契约：

1. **写入边界**：统一走 proxy；
2. **异步所有权**：cleanup abort + generation；
3. **资源所有权**：dispose -> scope.stop -> watcher cleanup/socket close。

### 8. 更正后的 import

```ts
import {
  effectScope,
  onScopeDispose,
  readonly,
  reactive,
  shallowRef,
  watch,
  watchEffect,
  type Ref,
} from 'vue'
```

教材中明确指出并修正无用 import，比让学习者复制后面对 lint 错误更可靠。

### 9. dispose 顺序

```text
dispose()
  -> disposed = true
  -> generation++，所有晚结果失去提交资格
  -> scope.stop()
       -> stop watchers/effects
          -> watch onStop cleanup
             -> AbortController.abort()
       -> run scope cleanups
          -> socket.close()
       -> stop child scopes
```

scope.stop 的内部顺序属于固定 tag 实现；业务正确性还由 disposed/generation 保证，不应只靠顺序巧合。

### 10. Deferred 工具

```ts
function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((ok, fail) => {
    resolve = ok
    reject = fail
  })
  return { promise, resolve, reject }
}
```

### 11. T1/T2 乱序测试

```ts
it('ignores T1 after T2 becomes current even when abort is ignored', async () => {
  const t1 = deferred<Ticket>()
  const t2 = deferred<Ticket>()
  const signals: AbortSignal[] = []

  const repository: Repository = {
    load: vi.fn((id, { signal }) => {
      signals.push(signal)
      return id === 'T1' ? t1.promise : t2.promise
    }),
  }

  const panel = mountPanel(
    {
      mode: 'live',
      liveCount: 0,
      archiveCount: 0,
      ticketId: 'T1',
    },
    repository,
  )

  panel.apply({ ticketId: 'T2' })
  expect(signals[0].aborted).toBe(true)

  t2.resolve({ id: 'T2', title: 'new' })
  await Promise.resolve()
  expect(panel.detail.value?.id).toBe('T2')

  t1.resolve({ id: 'T1', title: 'old' })
  await Promise.resolve()
  expect(panel.detail.value?.id).toBe('T2')

  panel.dispose()
})
```

真实测试可能需要 `flushPromises()` 或明确的 `waitFor`，取决于运行时 watch scheduler。关键是由你 resolve Promise，绝不 sleep 猜时间。

### 12. dispose 晚结果测试

```ts
it('does not commit after dispose', async () => {
  const pending = deferred<Ticket>()
  const repository: Repository = {
    load: vi.fn(() => pending.promise), // 故意忽略 signal
  }
  const panel = mountPanel(seed('T1'), repository)

  panel.dispose()
  panel.dispose() // 幂等
  pending.resolve({ id: 'T1', title: 'late' })
  await Promise.resolve()

  expect(panel.detail.value).toBeNull()
})
```

### 13. 分支 cleanup 测试

```ts
it('tracks only the active count branch', async () => {
  const paint = vi.mocked(paintCount)
  const panel = mountPanel(seed('T1'), resolvedRepository())

  paint.mockClear()
  panel.apply({ mode: 'archive' })
  const afterSwitch = paint.mock.calls.length

  panel.apply({ liveCount: 7 })
  expect(paint).toHaveBeenCalledTimes(afterSwitch)

  panel.apply({ archiveCount: 9 })
  expect(paint).toHaveBeenCalledTimes(afterSwitch + 1)

  panel.dispose()
})
```

这验证当前实例的条件 Link cleanup。若线上仍多次 paint，统计每次 paint 来自哪个 panel instance，通常会看到旧 detached instances。

### 14. 20 次生命周期测试

让 fake `connect` 维护 active callbacks：

```ts
it('returns resource counts to zero after repeated mount/dispose', () => {
  const sockets = createSocketHarness()
  vi.mocked(connect).mockImplementation(sockets.connect)

  for (let i = 0; i < 20; i++) {
    const panel = mountPanel(seed(`T${i}`), resolvedRepository())
    expect(sockets.activeCount()).toBe(1)
    panel.dispose()
    expect(sockets.activeCount()).toBe(0)
  }

  sockets.emit({ type: 'live-count', value: 99 })
  expect(paintCount).not.toHaveBeenCalled()
})
```

如果 `paintCount` 包含 mount 初次调用，进入循环前/每次 dispose 后清 mock，并只断言 emit 后增量。

### 15. 错误分支

```ts
it('reports only the current request error', async () => {
  const oldRequest = deferred<Ticket>()
  const newRequest = deferred<Ticket>()
  const panel = mountPanel(seed('T1'), sequenceRepository([
    oldRequest.promise,
    newRequest.promise,
  ]))

  panel.apply({ ticketId: 'T2' })
  oldRequest.reject(new Error('old failed'))
  await Promise.resolve()
  expect(panel.error.value).toBeNull()

  const currentError = new Error('current failed')
  newRequest.reject(currentError)
  await Promise.resolve()
  expect(panel.error.value).toBe(currentError)
  panel.dispose()
})
```

### 16. `onTrack/onTrigger` 证据

可在最小 `effect()` 复现里记录：

```ts
const events: Array<{ phase: 'track' | 'trigger'; type: string; key: unknown }> = []

const runner = effect(
  () => state.liveCount,
  {
    onTrack: event => events.push({
      phase: 'track', type: event.type, key: event.key,
    }),
    onTrigger: event => events.push({
      phase: 'trigger', type: event.type, key: event.key,
    }),
  },
)
```

raw 写后不应新增 trigger；proxy 写应新增 SET trigger。日志只放 key/type/安全 ID，不把整个生产 model 和个人数据写日志。

### 17. 为什么不改 `cleanupDeps()`

贸然 patch core 会：

- 对 raw 写毫无帮助，因为根本没进入 trigger；
- 对 Promise 乱序毫无帮助，因为 Link 不知道业务 request generation；
- 对 detached scope 无 owner 毫无帮助，因为 scope 按契约仍 active；
- 可能破坏所有条件 computed/effect 的正确性和性能；
- 让应用绑定私有 fork，升级困难。

只有纯 `@vue/reactivity` failing spec 显示同一个 subscriber 的 LCA 在新分支后仍存在，才有理由审查 cleanupDeps。

### 18. 如果真的发现 core bug，最小 patch 流程

1. 在 clean `v3.5.42` 建 branch；
2. 把 reproducer 缩成 10~30 行；
3. 放进最相关现有 spec，先确认红；
4. snapshot Link 只是诊断，最终测试优先断言公共行为；
5. 找到破坏的不变量；
6. 只改负责该不变量的最小函数；
7. 相关 spec 通过；
8. 全 `unit`/reactivity tests；
9. lint/typecheck；
10. clean baseline 与 patch benchmark；
11. 检查当前维护分支是否已有 commit；
12. 在 issue/PR 里写 tag、环境、before/after、回归测试。

不要从 3.6 main 复制整段实现回 3.5。minor 级内部结构可能已改变，正确 backport 需要维护者判断。

### 19. KeepAlive：pause 还是 stop

若面板暂时 deactivated：

- pause scope：不执行 effects，期间多次 state 变更恢复时合并为一次最新状态；socket 是否继续接收由你决定；
- stop：彻底 cleanup，重新 activated 时需重建 scope/连接；
- 保持 socket、暂停 paint：可把 socket 与视图 effects 分到不同 scopes；
- 需要每条事件：写入 event buffer/outbox，不能依赖 effect pause replay。

选择取决于资源费用、恢复速度、事件完整性和数据敏感性。

### 20. 宿主 raw model 桥接

如果宿主必须继续修改 rawModel，有四种选择：

| 方案 | 优点 | 风险/适用 |
|---|---|---|
| 显式 `apply(patch)` | 边界清楚、可验证 | 推荐微前端消息契约 |
| 宿主发事件 | 可审计、解耦 | 要处理顺序/版本/销毁 |
| `shallowRef(snapshot)` 整体替换 | 大不可变快照高效 | 深改必须替换 identity |
| 共享 store/proxy | 使用方便 | 版本、Vue runtime、owner 耦合高 |

不要既暴露 raw 允许直接写，又期望子应用 proxy 自动感知。

### 21. 有副作用请求

generation 只阻止旧响应写 UI，不会撤销服务端操作。对于发布、支付、创建任务：

- idempotency key；
- server version/expectedVersion；
- timeout 后按 operation ID 查询状态；
- 不盲重放不可幂等请求；
- 服务端授权和审计；
- UI 展示“结果未知/确认中”，而非武断失败。

### 22. 版本漂移复核

升级到新 patch 时：

```bash
git diff v3.5.42..NEW_TAG -- packages/reactivity/src
git diff v3.5.42..NEW_TAG -- packages/reactivity/__tests__
git diff v3.5.42..NEW_TAG -- packages/runtime-core/src/apiWatch.ts
```

重新执行：

- sourceTrace 临时 spec；
- conditional deps tests；
- computed chain tests；
- array/collection tests；
- watch cleanup/pause tests；
- effectScope stop/pause tests；
- 应用 panel regression tests。

若内部 snapshot 变了、公共行为测试仍通过，应更新源码笔记而不是让业务跟随私有结构。若公共行为变了，查 changelog/RFC/issue，并在迁移文档明确记录。

### 23. 最终复建

关掉答案后，独立写出：

```text
raw write为什么不触发
watch cleanup为什么仍需 generation
detached scope为什么不会自动 stop
conditional branch为什么会删除旧 Link
为什么这四件事属于不同责任层
```

能把“响应式依赖生命周期”“异步任务生命周期”“外部资源生命周期”分别画出来，才算真正具备源码级生产排障能力。
