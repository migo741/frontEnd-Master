# 第 16 章答案：把组件实例当作可验证的资源边界

> 本答案固定 Vue Core v3.5.42。源码插桩只能存在于本地 fork；产品代码只使用公开 API。若你选择了不同实现，只要所有权、失效、测试和 public/private 边界完整，也可以成立。

## 练习 1 参考答案：从 Component VNode 到 Mounted Instance

### 1. 五个对象的引用关系

```text
TraceCard component definition/type（模块级，可复用）
  ↑ initialVNode.type
initialVNode（父本轮 render 创建）
  ↔ initialVNode.component = internal instance
       ├─ type = TraceCard
       ├─ vnode = initialVNode
       ├─ parent/root/appContext
       ├─ props/attrs/slots
       ├─ setupState
       ├─ proxy → public render context
       ├─ scope/effect/job
       └─ subTree → <article> VNode

父 template ref
  → exposeProxy/public instance
  → 只看见 focus（以及 Vue 允许的 public surface）
```

组件更新会产生 next component VNode，但同 type+key 时 `nextVNode.component = oldVNode.component`，instance uid 保持。换 key 后旧 instance 真正 unmount，新建 uid。

### 2. 主调用链表

| 函数 | 关键输入 | 写入/输出 | 保持的不变量 |
| --- | --- | --- | --- |
| `mountComponent` | initial VNode、parent、container | `vnode.component`、调用 setup/render effect | 每次新挂载一个 instance |
| `createComponentInstance` | VNode、parent、Suspense | 空壳 instance、uid、root/appContext/options | parent/root 拓扑确定，字段有初值 |
| `setupComponent` | instance、SSR flag | props/attrs/slots，进入 stateful setup | 用户 setup 前输入已分类 |
| `initProps` | raw vnode props | `instance.props`、`instance.attrs` | 声明 props/listeners 与 attrs 分开 |
| `initSlots` | vnode children | normalized `instance.slots` | slot 以函数协议在 render 时调用 |
| `setupStatefulComponent` | instance | public proxy，调用 setup | 调用期 currentInstance/scope 正确 |
| `createSetupContext` | instance | attrs、slots、emit、expose | 暴露受 instance 所有权控制 |
| `handleSetupResult` | setup return | render 或 proxyRefs(setupState) | 只接受函数/对象作为有效结果 |
| `finishComponentSetup` | instance | 确定 render、应用 options | 最终存在可执行 render 路径 |
| `setupRenderEffect` | instance/container | effect/update/job，首次 render/patch | instance.subTree 对应上次提交树 |
| `renderComponentRoot` | instance | root VNode、fallthrough attrs | attrs 只能落到可确定 root |

源码阅读时还应标注异常分支：async setup 返回 Promise 后由 renderer/Suspense 协调；SSR 下部分 lifecycle 不注册；functional component 不运行同样的 stateful setup。

### 3. Props、attrs 与 emits 分类

父输入：

| raw key | 结果 | 原因 |
| --- | --- | --- |
| `ticket-id` | `props.ticketId` | 与声明 prop camelize 后匹配 |
| `active` | `props.active` | 声明 prop |
| `class` | attrs，最终 merge 到 root article | 未声明 prop |
| `data-track` | attrs，最终到 root article | 未声明 prop |
| `onSelect` | emit listener，不作为普通 fallthrough attr | 声明了 select emit |
| `onClick` | attrs/native listener | 未声明 click emit；绑定到 root 时成为 DOM listener |

如果组件也声明 `click` emit，`onClick` 会被组件事件契约消费，而不是无条件 fallthrough。这个行为是为什么 emits declaration 具有 runtime 意义。

`useAttrs()` 与 setup context attrs 指向运行时受控的 attrs view；不要把一次解构值当持续响应 ref。

### 4. Slots 的两个时点

```text
setupComponent → initSlots：把 vnode children normalize 为 slots functions
renderComponentRoot → 组件 render/compiled template：在子决定的位置调用 slot
```

slot 内容使用父作用域。父 slot 依赖变化会让相关 render 更新；子不能在 setup 顶层把 `slots.default()` 的 VNodes 永久缓存。

### 5. Public proxy 读取 `count`

`handleSetupResult` 把 `{ count }` 经 `proxyRefs` 放入 `instance.setupState`。compiled render 通过 public proxy/context 读取 `count`；第一次查找命中 setupState，access cache 记录来源，后续走快路径。模板自动 unwrap ref，所以显示数字而不是 Ref 对象。

这只是模板/public proxy 的访问语义：普通 TS 代码里 `count.value` 仍然明确存在。

### 6. expose 测试

```ts
const wrapper = mount(Parent)
const card = wrapper.vm.card

expect(typeof card.focus).toBe('function')
expect('count' in card).toBe(false)
expect('attrs' in card).toBe(false)
```

`wrapper.vm` 的测试便利类型与浏览器 template ref 可能有差异，最好通过父组件的公开引用或 `defineExpose` 类型验证，不要读 `wrapper.getComponent(...).vm.$` 的 internal instance。

### 7. 更新与重建

同 type+key 更新：

```text
instance uid       不变
instance.props     原对象被更新/保持响应入口
instance.attrs     更新
instance.slots     更新 normalized functions
instance.vnode     指向新 VNode
instance.subTree   render 后换成新 tree
setupState/count   保留
mounted            不重跑
updated            本轮 DOM commit 后运行
```

换 key：旧 scope stop、unmount hooks/外部 cleanup，新 instance 从 setup 开始；count 回初值后 mounted 增加。

### 8. 一个安全的插桩方式

不应在产品中新增全局 mutable trace。固定 fork 的测试可在 `createComponentInstance`、`setupComponent` 和 `setupRenderEffect` 附近调用由测试构建注入的 no-op sink：

```ts
interface TraceSink {
  push(event: ComponentTraceEvent): void
}

const componentTraceSink: TraceSink | undefined =
  __DEV__ ? (globalThis as { __VUE_COMPONENT_TRACE__?: TraceSink })
    .__VUE_COMPONENT_TRACE__ : undefined

componentTraceSink?.push({
  phase: 'instance-created',
  uid: instance.uid,
  typeName: getComponentName(instance.type) ?? 'Anonymous',
  parentUid: instance.parent?.uid ?? null,
})
```

注意：这只是实验草图。不要把新 global 写入正式 fork 发布。更稳妥的是在 Vue 自身 test file 内建立局部 probe，或使用断点、`onRenderTracked`、Devtools public tooling。

预期相对顺序：

```text
instance-created
props-ready
slots-ready
setup-enter
setup-exit
render-start
mounted
```

mounted 是 post-render，必须晚于首次 subtree patch。对于 async setup，setup-enter/exit 的定义要写清是“同步调用返回 Promise”还是“Promise resolved”；不要用同一名字混淆。

### 9. 应用层测试示例

```ts
it('reuses the instance for the same key and replaces it for a new key', async () => {
  const wrapper = mount(Parent, { props: { ticketId: 'T-42', cardKey: 'card' } })
  const firstToken = wrapper.get('[data-instance-token]').text()

  await wrapper.setProps({ ticketId: 'T-43' })
  expect(wrapper.get('[data-instance-token]').text()).toBe(firstToken)

  await wrapper.setProps({ cardKey: 'replacement' })
  expect(wrapper.get('[data-instance-token]').text()).not.toBe(firstToken)
})

it('falls through undeclared native click but consumes declared select', async () => {
  const onClick = vi.fn()
  const onSelect = vi.fn()
  const wrapper = mount(TraceCard, {
    attrs: { class: 'compact', 'data-track': 'ticket', onClick },
    props: { ticketId: 'T-42', onSelect },
  })

  const root = wrapper.get('article')
  expect(root.classes()).toContain('compact')
  expect(root.attributes('data-track')).toBe('ticket')

  await root.trigger('click')
  expect(onClick).toHaveBeenCalledTimes(1)

  await wrapper.get('button').trigger('click')
  expect(onSelect).toHaveBeenCalledWith('T-42')
})
```

点击 button 会冒泡到 article，可能同时触发 onClick；测试要明确是触发 root、stop propagation，还是接受两种事件都发生，不能把 DOM 冒泡与 component emit 混为一谈。

### 10. Public/internal 对照

| 需要依赖的行为 | 不应依赖的实现 |
| --- | --- |
| props readonly、attrs fallthrough 文档语义 | props/attrs 内部对象形态 |
| lifecycle 注册规则 | instance hook 缩写数组名 |
| defineExpose 的 public surface | `instance.exposed`/`exposeProxy` 字段 |
| 同 key/type 复用行为 | uid 数值或生成策略 |
| setup 同步上下文 | currentInstance 全局变量的具体保存方式 |

---

## 练习 2 参考答案：修复 KeepAlive 异步地图组件的资源泄漏

### 1. 先拆两类共享

SDK script/module loader 可以全应用 singleflight，因为它是只读代码资源；每个 widget instance、tenant data、listener、timer 必须属于各自 component instance。

```text
loadMapSdkOnce(): shared Promise<SDK>
TenantMap instance A: widget A + handles A
TenantMap instance B: widget B + handles B
```

共享 SDK 不等于共享 widget。把 raw widget 放模块单例会让 tenant、DOM host 和 lifecycle 串在一起。

### 2. 类型契约

```ts
export interface MapLocation {
  lat: number
  lng: number
}

export interface MapWidget {
  resize(): void
  refresh(signal: AbortSignal): Promise<void>
  focus(): void
  destroy(): void
  onSelect(callback: (location: MapLocation) => void): () => void
}

export interface MapSdk {
  mount(host: HTMLElement, options: { tenantId: string }): MapWidget
}

export type MapSdkLoader = (signal: AbortSignal) => Promise<MapSdk>

export type WidgetState =
  | { tag: 'idle' }
  | { tag: 'loading'; generation: number }
  | { tag: 'ready'; generation: number; tenantId: string }
  | { tag: 'failed'; generation: number; message: string }
  | { tag: 'disposed' }
```

### 3. Composable 核心实现

```ts
import {
  onActivated,
  onBeforeUnmount,
  onDeactivated,
  onMounted,
  readonly,
  ref,
  watch,
  type Ref,
} from 'vue'

export interface Clock {
  setInterval(callback: () => void, ms: number): unknown
  clearInterval(handle: unknown): void
}

export interface TenantMapController {
  host: Ref<HTMLElement | null>
  state: Readonly<Ref<WidgetState>>
  retry(): void
  focus(): void
  refresh(): Promise<void>
}

export function useTenantMap(input: {
  tenantId: () => string
  loadSdk: MapSdkLoader
  clock: Clock
  emitReady(tenantId: string): void
  emitFailed(payload: { tenantId: string; code: string }): void
  emitSelect(location: MapLocation): void
}): TenantMapController {
  const host = ref<HTMLElement | null>(null)
  const state = ref<WidgetState>({ tag: 'idle' })

  let widget: MapWidget | undefined
  let loadingController: AbortController | undefined
  let refreshController: AbortController | undefined
  let interval: unknown | undefined
  let removeSelect: (() => void) | undefined
  let listeningResize = false
  let mounted = false
  let active = false
  let disposed = false
  let generation = 0

  const onResize = (): void => widget?.resize()

  function stopActiveResources(reason: string): void {
    refreshController?.abort(reason)
    refreshController = undefined

    if (interval !== undefined) {
      input.clock.clearInterval(interval)
      interval = undefined
    }
    if (listeningResize) {
      window.removeEventListener('resize', onResize)
      listeningResize = false
    }
    removeSelect?.()
    removeSelect = undefined
  }

  function startActiveResources(): void {
    if (!active || !widget || disposed) return
    if (!listeningResize) {
      window.addEventListener('resize', onResize)
      listeningResize = true
    }
    if (!removeSelect) {
      removeSelect = widget.onSelect(input.emitSelect)
    }
    if (interval === undefined) {
      interval = input.clock.setInterval(() => void refresh(), 5_000)
    }
  }

  function destroyWidget(): void {
    stopActiveResources('widget destroyed')
    if (widget) {
      const owned = widget
      widget = undefined // 先清引用，使重复 cleanup 幂等
      owned.destroy()
    }
  }

  async function ensureWidget(): Promise<void> {
    if (!mounted || !active || disposed || widget || !host.value) return

    loadingController?.abort('new SDK load')
    const controller = new AbortController()
    loadingController = controller
    const currentGeneration = ++generation
    const tenantId = input.tenantId()
    state.value = { tag: 'loading', generation: currentGeneration }

    try {
      const sdk = await input.loadSdk(controller.signal)
      if (
        disposed ||
        !mounted ||
        !active ||
        controller.signal.aborted ||
        currentGeneration !== generation ||
        tenantId !== input.tenantId() ||
        !host.value
      ) {
        return
      }

      widget = sdk.mount(host.value, { tenantId })
      state.value = { tag: 'ready', generation: currentGeneration, tenantId }
      startActiveResources()
      input.emitReady(tenantId)
    } catch (cause) {
      if (
        !disposed &&
        !controller.signal.aborted &&
        currentGeneration === generation
      ) {
        state.value = {
          tag: 'failed',
          generation: currentGeneration,
          message: cause instanceof Error ? cause.message : String(cause),
        }
        input.emitFailed({ tenantId, code: 'sdk-load-failed' })
      }
    } finally {
      if (loadingController === controller) loadingController = undefined
    }
  }

  async function refresh(): Promise<void> {
    if (!active || !widget || disposed) return
    refreshController?.abort('new refresh')
    const controller = new AbortController()
    refreshController = controller
    const currentGeneration = generation
    try {
      await widget.refresh(controller.signal)
    } catch (cause) {
      if (!controller.signal.aborted && currentGeneration === generation) {
        input.emitFailed({
          tenantId: input.tenantId(),
          code: cause instanceof Error ? cause.name : 'refresh-failed',
        })
      }
    } finally {
      if (refreshController === controller) refreshController = undefined
    }
  }

  function retry(): void {
    if (disposed) return
    state.value = { tag: 'idle' }
    void ensureWidget()
  }

  function focus(): void {
    widget?.focus()
  }

  function restartForTenant(): void {
    generation += 1
    loadingController?.abort('tenant changed')
    loadingController = undefined
    destroyWidget()
    state.value = { tag: 'idle' }
    void ensureWidget()
  }

  onMounted(() => {
    mounted = true
    active = true
    void ensureWidget()
  })

  onActivated(() => {
    active = true
    if (widget) startActiveResources()
    else void ensureWidget()
  })

  onDeactivated(() => {
    active = false
    generation += 1
    loadingController?.abort('component deactivated')
    loadingController = undefined
    stopActiveResources('component deactivated')
    if (state.value.tag === 'loading') state.value = { tag: 'idle' }
  })

  watch(input.tenantId, restartForTenant)

  onBeforeUnmount(() => {
    if (disposed) return
    disposed = true
    mounted = false
    active = false
    generation += 1
    loadingController?.abort('component unmounted')
    loadingController = undefined
    destroyWidget()
    state.value = { tag: 'disposed' }
  })

  return { host, state: readonly(state), retry, focus, refresh }
}
```

实现选择：deactivate 时若 SDK 尚未完成，直接作废并在下次 activate 重新进入 `ensureWidget`。ES module/chunk loader 通常已缓存，正确性比保留一个失去 owner 的 continuation 更重要。也可以把 SDK Promise 提升为 application-scoped singleflight，但 component generation 仍要检查。

### 4. SFC 边界

```vue
<script setup lang="ts">
import { computed, useAttrs } from 'vue'

defineOptions({ inheritAttrs: false })

const props = defineProps<{
  tenantId: string
  interactive?: boolean
}>()

const emit = defineEmits<{
  ready: [payload: { tenantId: string }]
  failed: [payload: { tenantId: string; code: string }]
  'select-location': [payload: MapLocation]
}>()

const attrs = useAttrs()
const hostAttrs = computed(() => {
  const output: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(attrs)) {
    if (
      key === 'class' ||
      key === 'style' ||
      key === 'tabindex' ||
      key.startsWith('aria-') ||
      key.startsWith('data-')
    ) {
      output[key] = value
    }
  }
  return output
})

const map = useTenantMap({
  tenantId: () => props.tenantId,
  loadSdk,
  clock: browserClock,
  emitReady: tenantId => emit('ready', { tenantId }),
  emitFailed: payload => emit('failed', payload),
  emitSelect: location => emit('select-location', location),
})

defineExpose({ focus: map.focus, refresh: map.refresh })
</script>

<template>
  <section v-bind="hostAttrs" class="tenant-map">
    <div ref="map.host" class="tenant-map__canvas" aria-hidden="true" />
    <p v-if="map.state.value.tag === 'loading'" role="status">地图加载中…</p>
    <div v-else-if="map.state.value.tag === 'failed'" role="alert">
      地图加载失败
      <button type="button" @click="map.retry">重试</button>
    </div>
  </section>
</template>
```

模板中 refs 通常自动 unwrap；根据实际 SFC typing，模板可写 `map.state.tag`。这里展示 `.value` 是为了强调 composable 返回值形态，实施时以 `vue-tsc` 为准。

为什么过滤 attrs？这是一个 API 决策示例。由可信父组件传入的 `onClick` 本身不是 XSS，但如果组件承诺只把 ARIA/data/style 放到外壳，就应明确拒绝其余键，避免第三方 widget host 接受无意行为。另一种合法方案是完整 `v-bind="$attrs"`；关键是文档与测试一致。

`aria-label` 应在有语义的 section/region 上。内部 SDK canvas 若可交互，需要 SDK 自身提供键盘与可访问替代，不能简单 `aria-hidden`；题目实现应根据实际 widget 调整。

### 5. destroy 恰好一次的不变量

```text
widget undefined  → 没有 owned instance
mount succeeds    → widget = owned
destroyWidget     → 先 widget = undefined，再 owned.destroy()
重复 cleanup      → 看见 undefined，no-op
```

先清内部引用再调用 third-party destroy，可避免 destroy 同步触发 callback 又进入 cleanup 时重复销毁。

### 6. 关键测试设计

不用 sleep：

```ts
it('ignores A after B becomes current', async () => {
  const a = deferred<MapSdk>()
  const b = deferred<MapSdk>()
  const loadSdk = vi
    .fn<MapSdkLoader>()
    .mockImplementationOnce(() => a.promise)
    .mockImplementationOnce(() => b.promise)

  const wrapper = mountHarness({ tenantId: 'A', loadSdk })
  await wrapper.setProps({ tenantId: 'B' })

  b.resolve(fakeSdkB)
  await flushPromises()
  expect(fakeSdkB.mount).toHaveBeenCalledWith(expect.anything(), {
    tenantId: 'B',
  })

  a.resolve(fakeSdkA) // loader 故意忽略 abort
  await flushPromises()
  expect(fakeSdkA.mount).not.toHaveBeenCalled()
})
```

生命周期计数：

```ts
expect(activeIntervals()).toBe(1)
expect(resizeListenerBalance()).toBe(1)

deactivate()
expect(activeIntervals()).toBe(0)
expect(resizeListenerBalance()).toBe(0)

activate()
expect(activeIntervals()).toBe(1)
expect(resizeListenerBalance()).toBe(1)

wrapper.unmount()
expect(widget.destroy).toHaveBeenCalledTimes(1)
expect(activeIntervals()).toBe(0)
expect(resizeListenerBalance()).toBe(0)
```

不要直接手调组件内部私有 hook。通过一个动态 component + KeepAlive harness 切换，验证公开行为。

### 7. 错误边界

SDK loader 的预期失败可由组件状态显示；未知 render/widget adapter 错误再由上层 `onErrorCaptured` 提供局部 fallback。error boundary 本身只渲染静态安全内容并允许显式 retry/remount。

记录错误：component name、tenant id（若不敏感）、app version、SDK version、phase、request id。不要记录 token、完整地址或用户坐标。

### 8. 事故复盘示例结构

```text
触发：KeepAlive 页面首次打开后 SDK await；切页三次再淘汰
错误假设：await 后仍有 active instance；deactivate 会调用 unmounted
源码证据：setupStatefulComponent 调用期设置/reset currentInstance；
          apiLifecycle 把 hook 注入 current instance；KeepAlive 只 move/deactivate
影响：每次激活新增 listener/timer，旧 tenant 响应回写，内存与请求量增长
修复：同步注册 hooks；幂等 start/stop；abort+generation；destroy once；最小 expose
回归：fake clock、deferred late resolve、真实 KeepAlive harness、active handle census
监控：SDK load failure、active widget count、poll count per visible page、route leave 后请求数
```

### 9. 生产边界

这份实现还需要针对真实 SDK 决定：

- SDK module 是否可 safely singleflight；
- widget 是否支持暂停而非销毁；
- refresh 是否真正接受 AbortSignal；
- 页面隐藏/网络离线策略；
- SSR placeholder 与 client-only mount；
- CSP、第三方脚本 integrity/allowlist；
- 地理位置隐私与日志脱敏。

但无论 SDK 如何变化，核心不变量保持：**instance 拥有 widget，active 状态拥有活跃 handles，generation 决定异步结果是否仍有提交资格。**
