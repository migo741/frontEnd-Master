# 第 16 章练习：组件实例调用链与资源所有权

> 本章恰好两题。第一题追真实源码和实例状态；第二题修复生产级生命周期事故。源码固定 Vue Core v3.5.42，禁止把私有字段导入产品代码。

## 练习 1：从 Component VNode 到 Mounted Instance

### 场景

下面组件同时使用 props、attrs、slots、emit、provide/inject、expose 和生命周期：

```vue
<!-- TraceCard.vue -->
<script setup lang="ts">
import { inject, onMounted, provide, ref, useAttrs } from 'vue'
import { traceKey } from './keys'

const props = defineProps<{ ticketId: string; active?: boolean }>()
const emit = defineEmits<{ select: [id: string] }>()
const slots = defineSlots<{ default(props: { id: string }): unknown }>()
const attrs = useAttrs()
const count = ref(0)
const parentTrace = inject(traceKey, 'root')
provide(traceKey, `${parentTrace}/${props.ticketId}`)

function focus(): void {}
defineExpose({ focus })

onMounted(() => count.value++)
</script>

<template>
  <article v-bind="attrs" :data-ticket="ticketId">
    <slot :id="ticketId" />
    <button type="button" @click="emit('select', ticketId)">{{ count }}</button>
  </article>
</template>
```

父传入：

```vue
<TraceCard
  ref="card"
  ticket-id="T-42"
  class="compact"
  data-track="ticket"
  @select="handleSelect"
  @click="handleNativeClick"
>
  <template #default="{ id }">{{ id }}</template>
</TraceCard>
```

### 任务 A：源码调用链档案

以 v3.5.42 固定链接记录下列函数的输入、输出和不变量：

```text
renderer.mountComponent
createComponentInstance
setupComponent
initProps / initSlots
setupStatefulComponent
createSetupContext
handleSetupResult
finishComponentSetup
setupRenderEffect
renderComponentRoot
```

每个节点最多 5 行，但必须说明谁写了 instance 的哪些字段。画出 component definition、initialVNode、instance、proxy、subTree 的引用关系。

### 任务 B：开发 fork 插桩

在**本地固定 tag fork**中插入仅测试使用的 trace sink，至少记录：

```ts
export interface ComponentTraceEvent {
  phase:
    | 'instance-created'
    | 'props-ready'
    | 'slots-ready'
    | 'setup-enter'
    | 'setup-exit'
    | 'render-start'
    | 'mounted'
  uid: number
  typeName: string
  parentUid: number | null
  keys?: readonly string[]
}
```

你可以用 debugger/日志替代正式 sink，但最终必须输出可比较 JSON。不得发布修改后的 Vue 包。

### 任务 C：输入分类与 public surface

用测试回答：

- `ticketId/active`、class/data-track、onSelect、onClick 分别进入 props/attrs/emits 的哪一类；
- slot 是何时 normalize、何时调用；
- template 中 `count` 从哪个桶被 public proxy 读取；
- 父 template ref 最终能看见什么；
- `focus` 之外的内部 ref 是否暴露；
- 更新 ticketId/class/slot 后，instance uid 是否复用，哪些字段改变。

不要在业务测试里直接断言所有私有字段；私有观察只存在固定 fork 的源码实验，应用测试断言公开行为。

### 最少测试

- mount 与 update；
- 同 type+key 与换 key；
- declared emit listener 与 undeclared click listener；
- 单 root attr fallthrough；
- slot content 响应更新；
- expose surface；
- parent/child provide override；
- unmount 后 hook/effect 不再运行。

### 发散问题

1. 若 TraceCard 改成两个 root，attrs 应转发到哪里？
2. functional component 的 instance/setup 路径有何不同？
3. runtime-compiled template 与预编译 SFC 在 finishComponentSetup 处有何差异？
4. 为什么不应该把 instance.uid 当业务 ID？

### 交付物

- 调用链图与字段表；
- 固定 fork trace JSON 和最小 patch；
- VTU tests；
- public contract/internal detail 对照表。

---

## 练习 2：修复 KeepAlive 异步地图组件的资源泄漏

### 场景

`TenantMap.vue` 被路由页面放在 KeepAlive 中。它：

- await SDK 后才注册生命周期；
- 每次 activated 重复创建 resize listener 和 interval；
- deactivated 仍发送位置请求；
- `inheritAttrs: false` 后忘记把 `aria-label` 与 class 绑定到 canvas host；
- SDK 慢加载完成时，用户可能已切 tenant 或 cache eviction；
- widget 错误会穿过整个 app，没有局部 fallback；
- template ref 暴露了 raw SDK instance，父组件可以任意修改。

### 起始错误代码

```ts
async setup(props, { attrs, expose }) {
  const sdk = await loadSdk()
  const widget = sdk.mount('#map', { tenantId: props.tenantId })

  onActivated(() => {
    window.addEventListener('resize', widget.resize)
    setInterval(() => widget.refresh(), 5_000)
  })

  onUnmounted(() => widget.destroy())
  expose({ widget })
  return () => h('div', { id: 'map' })
}
```

### 任务 A：重构为同步 setup + 显式状态机

设计：

```ts
type WidgetState =
  | { tag: 'idle' }
  | { tag: 'loading'; generation: number }
  | { tag: 'ready'; generation: number; tenantId: string }
  | { tag: 'failed'; generation: number; message: string }
  | { tag: 'disposed' }
```

必须做到：

- 所有 hooks 在第一次 await 前同步注册；
- mounted/activated 双调用不会重复启动；
- deactivated 暂停 listener/timer/request；
- activated 恢复；
- tenantId 变化使旧 generation 失效并重建/更新 widget；
- unmount/eviction destroy 恰好一次；
- SDK loader 忽略 abort 时，晚结果也不能 mount；
- 错误进入局部可恢复 UI；
- public expose 只有 `focus()`、`refresh()`，没有 raw widget。

### 任务 B：attrs 与 events 契约

组件公开：

```ts
props: tenantId, interactive
emits:
  ready({ tenantId })
  failed({ tenantId, code })
  select-location({ lat, lng })
```

明确 attrs 应落到哪个 host；过滤或拒绝哪些不安全 attrs；class/style、aria-label、data-* 和 native listeners 怎样处理。多 root 错误 UI 时也不能丢失 accessible name。

### 任务 C：测试

使用 injected SDK loader、fake clock、deferred Promise 和 listener spy，覆盖：

- 首次 mount/activate 只有一个 listener 与 timer；
- deactivate 后归零，activate 后恢复为一个；
- A loader pending → 切 B → B ready → A late resolve，DOM/store 仍是 B；
- loader reject → retry；
- eviction/unmount destroy 一次；
- event payload 类型与 runtime validator；
- attrs 在真实 host；
- errorCaptured/fallback 自己不抛错；
- 测试结束无 active handles。

### 任务 D：事故复盘

按“触发条件 → 错误假设 → 源码证据 → 修复 → 回归 → 监控”写 800～1,500 字。至少引用 currentInstance、hook injection、instance scope、KeepAlive deactivate 四个机制。

### 发散问题

1. 多个地图组件是否应该共享一次 SDK script load？共享 loader 与共享 widget 有何区别？
2. 页面不可见但未 deactivated（后台 tab）时如何暂停？
3. SSR 时地图组件应输出什么，hydration 怎样避免 mismatch？
4. SDK 崩溃后重建 widget，怎样保证旧 DOM/listener 不残留？

### 交付物

- strict TypeScript composable/component 核心；
- 资源所有权表与状态图；
- 至少 10 个确定性测试；
- 事故复盘和源码固定链接。
