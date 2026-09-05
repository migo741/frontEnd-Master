# 第 17 章练习：固定 Tag 调用链与生产故障最小修复

> 只做两题。题 1 必须在 `v3.5.42` checkout 中完成；题 2 先证明是应用错误还是框架错误，再决定 patch 放哪。禁止用 `main` 的文件补答案。

## 题 1：手工追踪 Dep/Link/Subscriber，并做测试级插桩（机制题）

### 目标

对下面程序给出**真实 v3.5.42 调用链**，并用 test-only inspection 验证。不能画 `Set<effect>`。

```ts
import { computed, effect, reactive, stop, toRaw } from '@vue/reactivity'

const state = reactive({ useA: true, a: 1, b: 10 })
const selected = computed(() => (state.useA ? state.a : state.b))

let output = -1
const runner = effect(() => {
  output = selected.value
})

state.a = 2
state.a = 2
state.useA = false
state.a = 3
state.b = 11
stop(runner)
state.b = 12
```

### 固定环境契约

报告第一屏必须记录：

```text
tag: v3.5.42
expected release commit: d63616c
actual git rev-parse HEAD: ...
node: ...
pnpm: ...
working tree before instrumentation: clean
```

若 commit 不匹配，停止实验。不要“版本差不多就继续”。

### 手工追踪交付物

为以下七个检查点各画一张小图或表：

1. `effect()` 首次运行完成；
2. `state.a = 2` 的 notify 到 output 更新；
3. 第二次 `state.a = 2`；
4. `state.useA = false` 完成分支切换；
5. `state.a = 3`；
6. `state.b = 11`；
7. `stop(runner)` 后和 `state.b = 12` 后。

每个检查点至少写：

- `output`；
- `globalVersion` 是否推进及原因；
- `Dep(useA/a/b)` 是否存在；
- 三个 property Dep 的 version；
- `selected.dep.version`；
- outer effect 的 deps 链；
- computed 的 deps 链；
- 每个 Dep 的 subs 链；
- Link.version 与对应 Dep.version；
- computed flags 的相关状态；
- 是否进入 batch、是否真正执行 getter/effect。

数字 version 以你的实际 tag 运行结果为准；若开发/测试中额外读取了响应式值，说明它是否改变依赖图。

### Test-only 插桩

在 Vue 仓库内新增一个临时 spec，例如：

```text
packages/reactivity/__tests__/sourceTrace.spec.ts
```

允许从 `../src/dep`、`../src/computed` 读取内部类型。实现：

```ts
interface LinkSnapshot {
  depName: string
  depVersion: number
  linkVersion: number
}

function snapshotSubscriber(sub: Subscriber): LinkSnapshot[]
function snapshotDep(dep: Dep): string[]
function assertBidirectionalIntegrity(subs: Subscriber[], deps: Dep[]): void
```

约束：

- 不给生产 `Dep`/`Link` 增加字符串字段；
- 不把 inspection helper 导出到 `@vue/reactivity`；
- 用外部 `WeakMap<object, string>` 给对象命名；
- 遍历链表必须设最大节点数，发现环立即失败；
- 同时验证 `next.prev === current` 和 `prev.next === current`；
- 不序列化完整 target；
- spec 结束后不留下全局 monkey patch。

### 必须验证的机制

- [ ] outer effect 只订阅 `selected.dep`，不会直接订阅 `state.a`；
- [ ] computed 初始 deps 顺序是 `useA -> a`；
- [ ] 第一次 computed 求值后，消费者 Link.version 与 computed.dep.version 同步；
- [ ] 同值 SET 不推进对应 Dep，不执行 getter/effect；
- [ ] 切到 B 后 computed deps 顺序是 `useA -> b`；
- [ ] `a` 的旧 Link 同时从 computed.deps 和 Dep(a).subs 摘除；
- [ ] 若 `a` 无其他订阅者，property Dep 可从 depsMap 删除；
- [ ] `state.a = 3` 不改变 output，不触发 selected getter；
- [ ] `state.b = 11` 更新 output；
- [ ] stop 后 outer effect 从 selected.dep 解绑；
- [ ] 无消费者 computed 对 source deps 的内部订阅形态与源码一致；
- [ ] 手工图与插桩 snapshot 一致。

### 测试命令与范围

至少执行：

```text
pnpm vitest packages/reactivity/__tests__/sourceTrace.spec.ts --run
pnpm vitest packages/reactivity/__tests__/effect.spec.ts --run
pnpm vitest packages/reactivity/__tests__/computed.spec.ts --run
```

命令若因仓库 Vitest project 配置不同而需调整，记录实际命令，不要伪造成功输出。

### Benchmark 注意

本题的链表 snapshot 是重型诊断，禁止据此测性能。若你想比较：

1. 保留 clean checkout 作为 baseline；
2. inspection 只在测试文件，不改热路径；
3. 固定机器/Node/pnpm；
4. 多轮运行官方 reactivity bench；
5. 报告中位数/分布；
6. 不把一次运行差异称为回退。

### 发散

- 若在分支切换时访问顺序从 `useA -> a -> x` 变为 `x -> useA -> b`，哪些 Link 会复用、移动、新建、删除？
- 若 `selected` 同时被两个 effects 读取，computed.dep 的 subs 链和 source deps 的订阅数量如何变化？
- 最后一个消费者 stop 后，computed 为什么要 soft unsubscribe？再次读取时如何恢复？

---

## 题 2：定位一个“Vue 不更新、请求串台、离开后仍运行”的生产事故（生产开放题）

### 背景代码

一个微前端面板由宿主传入 raw model。每次进入路由都会调用 `mountPanel()`：

```ts
import {
  effectScope,
  reactive,
  ref,
  toRaw,
  watch,
  watchEffect,
} from 'vue'

interface PanelModel {
  mode: 'live' | 'archive'
  liveCount: number
  archiveCount: number
  ticketId: string
}

export function mountPanel(rawModel: PanelModel, repository: Repository) {
  const state = reactive(rawModel)
  const raw = toRaw(state)
  const detail = ref<Ticket | null>(null)
  const scope = effectScope(true)

  scope.run(() => {
    watchEffect(() => {
      paintCount(state.mode === 'live' ? state.liveCount : state.archiveCount)
    })

    watch(
      () => state.ticketId,
      async id => {
        detail.value = await repository.load(id)
      },
      { immediate: true },
    )
  })

  const socket = connect(message => {
    if (message.type === 'live-count') raw.liveCount = message.value
    if (message.type === 'select-ticket') state.ticketId = message.id
  })

  return { state, detail, socket }
}
```

路由组件卸载时只丢弃返回对象，没有调用其他方法。

线上现象：

1. WebSocket 的 live count 明明变化，UI 偶尔不更新；
2. 用户快速选 T1 再选 T2，T1 的慢响应最后覆盖 T2；
3. 反复进入离开 20 次后，一条消息触发多次 paint 和请求；
4. 团队声称是“Vue 条件依赖 cleanup 没删干净”，准备修改 `cleanupDeps()`。

### 任务 A：先归因，不准先改源码

为每个现象给出：

- 最小复现；
- 公共 API 层原因；
- v3.5.42 源码证据路径；
- 能否由 `onTrack/onTrigger` 观察；
- 它是 Vue core bug、应用 bug，还是证据不足；
- 最小回归测试。

你必须明确回答：“条件依赖 cleanup 是否真有证据出错？”

### 任务 B：提交最小应用 patch

patch 至少满足：

- 所有需要触发响应式更新的写入经过 proxy/ref；
- ticket 请求支持 cleanup + AbortSignal；
- 即使 repository 忽略 abort，旧结果也不能提交；
- scope/socket 有明确 owner 和 dispose；
- dispose 幂等；
- 路由卸载后不再 paint、请求或写 detail；
- 不把 detached scope 换成另一个无人 stop 的全局单例；
- 不访问 Dep/Link 私有字段修业务 bug。

公开返回契约建议改为：

```ts
interface MountedPanel {
  state: PanelModel
  detail: Readonly<Ref<Ticket | null>>
  dispose(): void
}
```

### 失败语义

| 场景 | 期望 |
|---|---|
| raw host model 外部直接改变 | 必须明确“不响应”或提供受控 `apply()` 入口，不能偶发 |
| T1 慢、T2 快 | 只允许 T2 提交 |
| abort 被忽略 | generation 仍阻止 T1 提交 |
| load 失败 | 当前请求显示/上报错误，旧请求错误被忽略 |
| dispose 时请求在途 | abort，晚结果不提交 |
| dispose 调两次 | 不抛错、不重复副作用 |
| 重新 mount | 只有新实例响应消息 |

### 必须写的测试

- [ ] raw 写不会触发 onTrigger，用它证明第一症状而非猜测；
- [ ] proxy 写会触发并更新 paint；
- [ ] `mode: live -> archive` 后，liveCount 不再触发当前实例，archiveCount 会触发；
- [ ] 用可控 deferred Promise 复现 T1/T2 乱序；
- [ ] repository 忽略 AbortSignal 时 generation 仍正确；
- [ ] dispose 后修改 state 不再 paint；
- [ ] dispose 后 resolve 请求不写 detail；
- [ ] 20 次 mount/dispose 后 active socket/effect 数回到零；
- [ ] 两次 dispose 幂等；
- [ ] 没有依赖 sleep。

### 若你仍认为是 Vue core bug

必须先完成：

1. 删除 socket/repository/微前端，只用 `@vue/reactivity` 复现；
2. checkout `v3.5.42`；
3. 在最相关官方 spec 中增加一个**失败测试**；
4. 展示 Link 双链哪条不变量破坏；
5. 给出最小 source patch；
6. 跑相关和全量 reactivity tests；
7. 跑无插桩 benchmark；
8. 对比 `v3.5.43+`/相关 issue 是否已有修复；
9. 不把对 `main` 有效的 patch 直接 backport 到 3.5.42。

### 验收

- [ ] 修复优先落在真正责任层；
- [ ] 使用固定 tag 源码解释，而非 Set 模型；
- [ ] cleanup、scope、request generation 三种生命周期没有混为一谈；
- [ ] patch 小而完整，有测试证明每条失败边；
- [ ] 没有为了“性能”绕过 proxy；
- [ ] 没有把 Abort 当作唯一正确性门；
- [ ] 记录精确 Vue 版本和测试命令；
- [ ] 说明升级后怎样做版本漂移审计。

### 发散

- 如果宿主必须继续持有并修改 rawModel，桥接协议应选事件、显式 patch、shallowRef replacement 还是共享 store？比较边界。
- 如果面板 KeepAlive 只是暂时失活，应该 pause scope 还是 stop/recreate？列出对 WebSocket、缓存和中间事件的语义。
- 如果请求不可取消且有服务端副作用，generation 只保护 UI，还需要什么幂等与最终状态协议？
