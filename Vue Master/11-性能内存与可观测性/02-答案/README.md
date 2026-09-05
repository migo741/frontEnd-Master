# 第 11 章答案：性能证据链与资源所有权

> 答案不是唯一实现。可复写的核心是：假设 → 证据 → 最小改动 → 同条件复测 → 预算与回退。

## 题 1 参考答案：五天内救回 OpsBoard

### 1. 诊断顺序

**第一步：RUM 分段，确认影响面。**

按 `/operations`、release、移动/桌面、网络类型、数据规模、是否命中缓存切片 LCP 与 INP。它回答问题是否集中在弱机/特定 release，并避免用开发者高配机器代表用户。检查 CLS 已经良好，五天内不优先动它。

**第二步：固定场景的 Network + Performance。**

在与 p75 接近的手机 CPU/网络条件下，用相同账号冷启动并录制：HTML、CSS、JS、字体、LCP 图片的 waterfall；看图表库是否在首屏下载、解析和执行；标记 LCP 元素及其资源发现时间。然后录制一次“输入一个筛选字符”，拆开 handler、排序/过滤、Vue render/patch、style/layout。

**第三步：Vue 更新链。**

Vue Devtools 已提示 8,000 行更新。再验证新对象 props 和全量 `selectedId` 是否是触发源；必要时用 `onRenderTriggered` 在少量 fixture 上确认。比较 `TicketRow` render 时间、DOM 数和 layout，判断虚拟化收益是否大于纯 props 稳定化。

因果链可写为：

```text
LCP:
首屏同步 import 图表
 → 700KB 网络 + parse/execute
 → 主线程阻塞 Vue mount/关键数据处理
 → LCP 元素晚绘制

INP:
input
 → 对 20k 行同步 filter/sort
 → 父 render 创建 20k 新 ticket 对象
 → selectedId 让每行 props 参与变化
 → 8k+ 子组件 render/patch + 大量 DOM layout
 → 下一帧延迟
```

若 trace 表明 LCP 元素是晚到的后端数据而非 JS 阻塞，第一条只是相关性而非根因；这就是必须记录反证的原因。

### 2. 最多三项改动

#### 改动 A：把折叠图表变成有状态的异步边界

```vue
<script setup lang="ts">
import { defineAsyncComponent, ref } from 'vue'

const opened = ref(false)
const ReportCharts = defineAsyncComponent({
  loader: () => import('./ReportCharts.vue'),
  timeout: 15_000,
})
</script>

<template>
  <button :aria-expanded="opened" @click="opened = !opened">图表</button>
  <Suspense v-if="opened">
    <ReportCharts />
    <template #fallback><p role="status">正在加载图表…</p></template>
  </Suspense>
</template>
```

证据明确指出它不属于首屏，却占主要体积与执行时间。可在用户高概率打开时通过 hover/idle 预取，但应测是否影响关键资源优先级。

#### 改动 B：稳定行协议

```vue
<TicketRow
  v-for="ticket in visibleTickets"
  :key="ticket.id"
  :ticket="ticket"
  :selected="ticket.id === selectedId"
/>
```

```ts
interface TicketSummary {
  readonly id: string
  readonly title: string
  readonly status: 'open' | 'closed'
  readonly version: number
}

defineProps<{ ticket: TicketSummary; selected: boolean }>()
```

数据层按实体变更替换对象，未变化实体保持同一引用。`selectedId` 改变时，只有旧选中行和新选中行的布尔 props 改变。先不用 `v-memo`；若 profile 仍证明 render 昂贵，再让 `ticket.version` 成为显式失效协议。

#### 改动 C：成熟虚拟化方案 + 可访问降级

20,000 行 DOM 本身会增加 patch/layout。固定行高时使用窗口化：

```ts
const start = computed(() =>
  Math.max(0, Math.floor(scrollTop.value / ROW_HEIGHT) - OVERSCAN),
)
const end = computed(() =>
  Math.min(
    filtered.value.length,
    Math.ceil((scrollTop.value + viewportHeight.value) / ROW_HEIGHT) + OVERSCAN,
  ),
)
const visibleTickets = computed(() => filtered.value.slice(start.value, end.value))
const translateY = computed(() => start.value * ROW_HEIGHT)
const totalHeight = computed(() => filtered.value.length * ROW_HEIGHT)
```

生产实现需要成熟库、稳定 key、focus roving、overscan、滚动到选中项、`aria-rowindex`/`aria-rowcount` 和动态高度策略。若产品必须让读屏一次浏览整张语义表，选服务端分页或提供“可访问分页视图”，而不是宣称虚拟 DOM 中不存在的行可被读出。

为何未把 Worker 放前三：要先看过滤计算占比。若计算长任务远大于 patch/layout，Worker 可替换第三项或与虚拟化并行规划；但五天限制下必须依据 trace 排序。

### 3. 三层预算

这些数字是示例，应由当前基线和产品 SLO 确认：

| 阶段 | 检查 | 示例失败条件 |
| --- | --- | --- |
| PR | bundle diff + 关键组件基准 + 测试 | 初始 JS > 400KB gzip；图表进入 initial chunk；一次选择更新 > 10 行 |
| 预发 | 固定弱机/网络 trace | LCP > 2.8s；筛选 Long Task > 150ms；DOM > 1,000；键盘回归 |
| 灰度 | RUM + 业务指标 | 移动 p75 LCP > 2.5s 或 INP > 200ms；错误率/搜索成功率恶化 |

灰度应关联 release/flag。若性能未改善或错误、可访问性、筛选正确率恶化，关闭 flag/回滚；不要为了守住数字牺牲功能。

### 4. 反证与下一步

1. 图表异步后 LCP 不变：查 LCP 资源发现、API TTFB、关键 CSS/图片，而不是继续拆包。
2. 稳定 props 后仍更新 8,000 行：查 slot、provide/inject、全局 store selector 或父级 key 是否使子树重建。
3. Vue render 很短但 INP 差：查同步过滤、第三方 handler、layout/paint 和浏览器扩展。
4. 虚拟化后 CPU 降但 INP 不降：检查动态测量导致的 layout thrashing、scroll handler 与计算任务。
5. p75 改善但 p95 恶化：按低端设备、超大账号和网络继续切片，可能需要服务端分页/索引。
6. Lab 改善、RUM 不变：检查灰度覆盖、缓存、真实用户旅程与埋点版本。

### 5. ADR 结论示例

当完整表格语义不可被虚拟化库保证时，可提供默认高性能虚拟视图和可切换的服务端分页无障碍视图。决策记录用户群、数据量、读屏需求、浏览器查找、SEO/打印、维护成本与后端能力；不是简单选“最快”的方案。

## 题 2 参考答案：地图页泄漏

### 1. 可重复调查

固定同一 GeoJSON、marker 数量、账号和浏览器版本：

1. 直接访问列表，等待空闲，取 baseline heap；
2. 进入地图，等待 markers 完成，触发一次 resize 和一次 marker click；
3. 返回列表。因为有 KeepAlive，此时是 deactivate，不是 unmount；
4. 重复 10 次，每轮等待相同时间；
5. 在 DevTools 开放的测试环境执行 GC，取 comparison snapshot；
6. 记录 `MapSdkInstance`、`ResizeObserver`、WebSocket、Detached Element、组件实例、listener 数量和 retained size；
7. 另做一组移除 KeepAlive 或真正销毁路由的测试，区分缓存设计与泄漏。

### 2. retained path 候选

| 对象 | 可能 owner |
| --- | --- |
| detached canvas/marker DOM | SDK 内部 registry 或未 destroy 的 map instance |
| 组件闭包 | `window.resize` listener registry |
| 元素与组件 | `ResizeObserver` callback/observed target |
| 大 GeoJSON | timer callback、未完成请求、store 无界缓存 |
| marker handler | SDK event bus；每次 activate 重复 on |
| socket callback | WebSocket listener，即使 close 也可能未解除自定义引用 |
| route component | KeepAlive cache；可能是预期持有，但其活动资源不应继续增长 |
| 旧 session | promise then/catch 闭包或 AbortController 未取消 |

### 3. 可复写的生命周期骨架

```ts
import {
  onActivated,
  onBeforeUnmount,
  onDeactivated,
  onMounted,
  shallowRef,
  type Ref,
} from 'vue'

interface MapSdk {
  destroy(): void
  on(type: 'marker-click', handler: (id: string) => void): void
  off(type: 'marker-click', handler: (id: string) => void): void
}

interface MapFactory {
  create(element: HTMLElement): MapSdk
}

export function useMapSession(
  host: Ref<HTMLElement | null>,
  factory: MapFactory,
) {
  const status = shallowRef<'idle' | 'running' | 'stopped'>('idle')
  let sdk: MapSdk | undefined
  let observer: ResizeObserver | undefined
  let socket: WebSocket | undefined
  let pollTimer: ReturnType<typeof setInterval> | undefined
  let aborter: AbortController | undefined
  let generation = 0

  const onWindowResize = (): void => {
    // 只调度必要的 SDK resize；生产中可 RAF 合并。
  }
  const onMarkerClick = (id: string): void => console.debug('marker', id)

  async function refresh(signal: AbortSignal, ownGeneration: number): Promise<void> {
    const response = await fetch('/api/map/markers', { signal })
    if (!response.ok) throw new Error(`markers: ${response.status}`)
    const data: unknown = await response.json()
    if (signal.aborted || ownGeneration !== generation || status.value !== 'running') return
    // validate(data)，再交给仍存活的 sdk
  }

  function start(): void {
    if (status.value === 'running') return
    const element = host.value
    if (!element) return
    generation += 1
    const ownGeneration = generation
    status.value = 'running'
    aborter = new AbortController()
    sdk = factory.create(element)
    sdk.on('marker-click', onMarkerClick)
    observer = new ResizeObserver(onWindowResize)
    observer.observe(element)
    window.addEventListener('resize', onWindowResize)
    socket = new WebSocket('wss://example.invalid/map')
    pollTimer = setInterval(() => {
      if (!aborter?.signal.aborted) {
        void refresh(aborter.signal, ownGeneration).catch((error: unknown) => {
          if (!(error instanceof DOMException && error.name === 'AbortError')) console.error(error)
        })
      }
    }, 5_000)
    void refresh(aborter.signal, ownGeneration)
  }

  function stop(): void {
    if (status.value !== 'running') return
    generation += 1
    status.value = 'stopped'
    aborter?.abort()
    aborter = undefined
    if (pollTimer !== undefined) clearInterval(pollTimer)
    pollTimer = undefined
    window.removeEventListener('resize', onWindowResize)
    observer?.disconnect()
    observer = undefined
    socket?.close()
    socket = undefined
    sdk?.off('marker-click', onMarkerClick)
    sdk?.destroy()
    sdk = undefined
  }

  onMounted(start)
  onActivated(start)
  onDeactivated(stop)
  onBeforeUnmount(stop)
  return { status, start, stop }
}
```

`start/stop` 幂等，generation 防止旧 promise 在新 session 中提交。真实项目还要验证响应 schema、处理 socket error/backoff、SDK create 失败的部分初始化回滚。

### 4. 验收与反证

“不是泄漏”的反证：显式 GC 后 retained instances 不随循环增长，内存在前几轮缓存/JIT 预热后进入平台；真正 unmount 后组件和 SDK 可释放。即便总 RSS 不立刻还给操作系统，只要 JS heap 中对象不可达，也不等价于泄漏。

修复验收：

- 重复 20 次 deactivate/activate，SDK 活跃实例始终为 0 或 1；
- resize、marker listener、timer、socket 数量不随循环增长；
- GC 后 heap 围绕稳定平台波动，业务约定容差内无单调增长；
- deactivate 时不再渲染/轮询，activate 后只建立一个 session；
- marker 点击恰好处理一次；网络慢响应不会更新旧页面。

### 5. 防回归测试

为 factory、timer、listener 封装注入计数器，做 20 次 lifecycle：

```ts
expect(resourceCounts.maps).toBe(1)
expect(resourceCounts.sockets).toBe(1)

await deactivatePage()
expect(resourceCounts.maps).toBe(0)
expect(resourceCounts.sockets).toBe(0)

await activatePage()
expect(resourceCounts.maps).toBe(1)
expect(markerHandler).toHaveBeenCalledTimes(1)
```

浏览器 E2E 再使用 Chrome DevTools Protocol 采集 DOM/listener/heap 趋势；单测证明 cleanup 被调用，E2E 才验证第三方 SDK 真的释放。

### 6. 发散题参考

将数据连接提升到应用级 `AlertStream` store/service，按登录会话拥有；地图组件只订阅已规范化的数据，并在 deactivate 后停止 view effect、SDK、observer。后台告警可继续进入有限队列/Pinia，而昂贵的 marker render 完全属于页面 session。两个所有者的生命周期和容量上限必须分别记录。

## 复写检查

合上答案后，至少能独立重写：

1. “RUM → trace → Vue trigger → before/after”的四段证据链；
2. 稳定 props 与虚拟窗口的关键代码；
3. 一个幂等的 `start/stop` 资源所有者；
4. 泄漏的 retained path 与平台值验收；
5. PR、预发、灰度三层性能预算。
