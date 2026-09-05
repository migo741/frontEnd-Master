# 第 02 章答案：keyed diff 与异步工作区

## 练习 1 参考答案：keyed patch 计划

### 1. 推导

先建立 `oldKey → oldIndex`，再按新顺序生成序列：

```text
old: A B C D
new: B E D A
旧索引 + 1: 2 0 4 1   （0 表示全新节点）
忽略 0 后，一个 LIS 是 2,4，对应 B,D
=> B,D 不动；A 需要 move；E 需要 mount；C unmount
```

`+1` 是为了把合法旧索引 0 与“新节点”标记 0 分开。

### 2. 实现

```ts
// planKeyedPatch.ts
export type PatchOp =
  | { type: 'patch'; key: string; oldIndex: number; newIndex: number }
  | { type: 'mount'; key: string; newIndex: number; beforeKey: string | null }
  | { type: 'unmount'; key: string; oldIndex: number }
  | { type: 'move'; key: string; newIndex: number; beforeKey: string | null }

export class DuplicateKeyError extends Error {
  constructor(
    readonly key: string,
    readonly side: 'old' | 'new',
  ) {
    super(`Duplicate key "${key}" in ${side} children`)
    this.name = 'DuplicateKeyError'
  }
}

function indexUnique(
  keys: readonly string[],
  side: 'old' | 'new',
): Map<string, number> {
  const result = new Map<string, number>()
  keys.forEach((key, index) => {
    if (result.has(key)) throw new DuplicateKeyError(key, side)
    result.set(key, index)
  })
  return result
}

// 返回 source 中构成 LIS 的“位置”，忽略值 0。
export function lisPositions(source: readonly number[]): readonly number[] {
  const predecessors = new Array<number>(source.length).fill(-1)
  const tails: number[] = [] // tails[length - 1] = source 中的最优结尾位置

  for (let i = 0; i < source.length; i++) {
    const value = source[i]!
    if (value === 0) continue

    let left = 0
    let right = tails.length
    while (left < right) {
      const middle = (left + right) >>> 1
      const tailValue = source[tails[middle]!]!
      if (tailValue < value) left = middle + 1
      else right = middle
    }

    if (left > 0) predecessors[i] = tails[left - 1]!
    tails[left] = i
  }

  if (tails.length === 0) return []
  const result = new Array<number>(tails.length)
  let cursor = tails.at(-1)!
  for (let i = result.length - 1; i >= 0; i--) {
    result[i] = cursor
    cursor = predecessors[cursor]!
  }
  return result
}

export function planKeyedPatch(
  oldKeys: readonly string[],
  newKeys: readonly string[],
): readonly PatchOp[] {
  const oldIndexByKey = indexUnique(oldKeys, 'old')
  const newIndexByKey = indexUnique(newKeys, 'new')
  const operations: PatchOp[] = []
  const oldIndexPlusOneByNewIndex = new Array<number>(newKeys.length).fill(0)

  // 先 patch 所有复用节点，并建立映射。
  newKeys.forEach((key, newIndex) => {
    const oldIndex = oldIndexByKey.get(key)
    if (oldIndex === undefined) return
    oldIndexPlusOneByNewIndex[newIndex] = oldIndex + 1
    operations.push({ type: 'patch', key, oldIndex, newIndex })
  })

  // 删除旧侧独有节点。
  oldKeys.forEach((key, oldIndex) => {
    if (!newIndexByKey.has(key)) {
      operations.push({ type: 'unmount', key, oldIndex })
    }
  })

  const stableNewPositions = new Set(lisPositions(oldIndexPlusOneByNewIndex))

  // 从右到左，右邻居可作为已稳定 anchor。
  for (let newIndex = newKeys.length - 1; newIndex >= 0; newIndex--) {
    const key = newKeys[newIndex]!
    const beforeKey = newKeys[newIndex + 1] ?? null
    if (oldIndexPlusOneByNewIndex[newIndex] === 0) {
      operations.push({ type: 'mount', key, newIndex, beforeKey })
    } else if (!stableNewPositions.has(newIndex)) {
      operations.push({ type: 'move', key, newIndex, beforeKey })
    }
  }

  return operations
}
```

### 3. 测试不应绑定唯一 LIS

```ts
import { describe, expect, it } from 'vitest'
import {
  DuplicateKeyError,
  lisPositions,
  planKeyedPatch,
  type PatchOp,
} from './planKeyedPatch'

const count = (ops: readonly PatchOp[], type: PatchOp['type']) =>
  ops.filter(op => op.type === type).length

describe('planKeyedPatch', () => {
  it('handles mixed patch/mount/unmount with minimum moves', () => {
    const ops = planKeyedPatch(['A', 'B', 'C', 'D'], ['B', 'E', 'D', 'A'])
    expect(count(ops, 'patch')).toBe(3)
    expect(count(ops, 'mount')).toBe(1)
    expect(count(ops, 'unmount')).toBe(1)
    // 复用序列 2,4,1 的 LIS 长度为 2，所以只移动 1 个。
    expect(count(ops, 'move')).toBe(1)
  })

  it('does not move a pure append', () => {
    const ops = planKeyedPatch(['A', 'B'], ['A', 'B', 'C'])
    expect(count(ops, 'move')).toBe(0)
    expect(ops).toContainEqual({
      type: 'mount', key: 'C', newIndex: 2, beforeKey: null,
    })
  })

  it('moves n-1 nodes for a full reverse', () => {
    const ops = planKeyedPatch(['A', 'B', 'C'], ['C', 'B', 'A'])
    expect(count(ops, 'move')).toBe(2)
  })

  it('unmounts everything', () => {
    expect(count(planKeyedPatch(['A', 'B'], []), 'unmount')).toBe(2)
  })

  it('mounts everything right-to-left with anchors', () => {
    const mounts = planKeyedPatch([], ['A', 'B'])
      .filter((op): op is Extract<PatchOp, { type: 'mount' }> => op.type === 'mount')
    expect(mounts).toEqual([
      { type: 'mount', key: 'B', newIndex: 1, beforeKey: null },
      { type: 'mount', key: 'A', newIndex: 0, beforeKey: 'B' },
    ])
  })

  it('rejects duplicate old keys', () => {
    expect(() => planKeyedPatch(['A', 'A'], ['A']))
      .toThrow(DuplicateKeyError)
  })

  it('rejects duplicate new keys', () => {
    expect(() => planKeyedPatch(['A'], ['A', 'A']))
      .toThrow('Duplicate key "A" in new children')
  })

  it('returns positions and ignores zeros in LIS', () => {
    const positions = lisPositions([2, 0, 4, 1])
    expect(positions.map(index => [2, 0, 4, 1][index])).toEqual([2, 4])
  })
})
```

LIS 可能不唯一，所以更稳的断言是：所有节点最终顺序正确、移动数等于 `复用数 - LIS长度`，而不是死绑某个等价移动序列。

### 4. 常见错解与限制

- 对每个新 key 用 `oldKeys.indexOf`：退化到 O(n²)。
- 把新节点的 0 也交给 LIS：会污染递增关系。
- 正向 move：目标右侧 anchor 可能尚未就位。
- 所有位置不同都 move：没有利用相对顺序，移动数不最少。
- 本实现没有 VNode type、Fragment、transition、组件生命周期和真实 DOM anchor；它是算法练习，不是 renderer。

---

## 练习 2 参考答案：异步报表工作区

### 1. 边界职责表

| 边界 | 拥有什么 | 不负责什么 |
| --- | --- | --- |
| `WorkspaceHost` | tab 身份、缓存、全屏开关、组件选择 | 面板业务请求细节 |
| `KeepAlive` | 最多 2 个面板实例生命周期 | 服务端数据缓存 |
| `AsyncPanelBoundary` | pending 延迟、后代错误 fallback、人工 retry | 把业务 4xx 变成异常 |
| async component | designer chunk 加载、超时、有限自动重试 | 报表数据加载 |
| panel | 草稿、滚动、轮询所有权 | 全局 overlay 层级 |
| Teleport dialog | 全屏 DOM 位置、焦点协议 | 改变 Vue 逻辑父子关系 |

### 2. 可暂停轮询

```ts
// usePausablePolling.ts
import { onActivated, onDeactivated, onUnmounted } from 'vue'

export function usePausablePolling(
  task: () => void | Promise<void>,
  intervalMs: number,
) {
  let timer: ReturnType<typeof setInterval> | null = null
  let disposed = false

  const start = (): void => {
    if (disposed || timer !== null) return
    timer = setInterval(() => void task(), intervalMs)
  }

  const pause = (): void => {
    if (timer === null) return
    clearInterval(timer)
    timer = null
  }

  const dispose = (): void => {
    if (disposed) return
    disposed = true
    pause()
  }

  onActivated(start)
  onDeactivated(pause)
  onUnmounted(dispose)

  // 首次正常挂载也要启动；start 幂等，activated 再调用无害。
  start()
  return { pause, start, dispose }
}
```

快捷键遵循同一 `start/pause/dispose` 幂等结构。不要在 activated 中匿名 addEventListener、deactivated 中创建另一个匿名函数 remove。

### 3. 异步组件工厂

```ts
// DesignerPanel.async.ts
import { defineAsyncComponent, type Component } from 'vue'
import ChunkLoadError from './ChunkLoadError.vue'

export function createDesignerPanel(): Component {
  return defineAsyncComponent({
    loader: () => import('./DesignerPanel.vue'),
    errorComponent: ChunkLoadError,
    timeout: 15_000,
    suspensible: true,
    onError(error, retry, fail, attempts) {
      const retryable = /fetch|network|loading chunk/i.test(error.message)
      if (retryable && attempts <= 1) retry()
      else fail()
    },
  })
}
```

工厂每次人工 retry 返回新的 async wrapper，避免已失败 wrapper 的缓存语义不透明。自动 retry 只有一次，人工 retry 由边界明确发起。

### 4. 异步与错误边界

```vue
<!-- AsyncPanelBoundary.vue -->
<script setup lang="ts">
import { onBeforeUnmount, onErrorCaptured, ref } from 'vue'

const emit = defineEmits<{ retry: [] }>()
const error = ref<Error | null>(null)
const showFallback = ref(false)
let fallbackTimer: ReturnType<typeof setTimeout> | null = null

function onPending(): void {
  error.value = null
  showFallback.value = false
  if (fallbackTimer) clearTimeout(fallbackTimer)
  fallbackTimer = setTimeout(() => { showFallback.value = true }, 150)
}

function settle(): void {
  if (fallbackTimer) clearTimeout(fallbackTimer)
  fallbackTimer = null
  showFallback.value = false
}

onErrorCaptured((cause) => {
  settle()
  error.value = cause
  return false
})

onBeforeUnmount(settle)

function retry(): void {
  error.value = null
  emit('retry')
}
</script>

<template>
  <section v-if="error" role="alert" aria-live="assertive">
    <h2>模块加载失败</h2>
    <p>{{ error.message }}</p>
    <button type="button" @click="retry">重试</button>
  </section>

  <Suspense v-else @pending="onPending" @resolve="settle" @fallback="onPending">
    <slot />
    <template #fallback>
      <slot v-if="showFallback" name="fallback">
        <p role="status">正在加载…</p>
      </slot>
    </template>
  </Suspense>
</template>
```

说明：边界将后代抛出的技术异常转为 fallback；正常的接口 404/权限失败应由 panel 的业务状态渲染，不应全抛给 error captured。生产项目若不接受 Suspense 实验性，可保留这个边界契约，把内部替换为显式 loader 状态机。

### 5. Host 核心

```vue
<!-- WorkspaceHost.vue -->
<script setup lang="ts">
import { computed, nextTick, ref, shallowRef } from 'vue'
import PreviewPanel from './PreviewPanel.vue'
import RunsPanel from './RunsPanel.vue'
import AsyncPanelBoundary from './AsyncPanelBoundary.vue'
import { createDesignerPanel } from './DesignerPanel.async'

export type TabId = 'preview' | 'designer' | 'runs'
export interface WorkspaceTab { id: TabId; reportId: string }

const props = defineProps<{ modelValue: WorkspaceTab }>()
defineEmits<{ 'update:modelValue': [next: WorkspaceTab] }>()

const fullscreen = ref(false)
const fullscreenTrigger = shallowRef<HTMLButtonElement | null>(null)
const designerVersion = ref(0)
const designerComponent = shallowRef(createDesignerPanel())

const panel = computed(() => {
  if (props.modelValue.id === 'preview') return PreviewPanel
  if (props.modelValue.id === 'runs') return RunsPanel
  // 读取 version 只是明确 retry 代次；组件本身保存在 shallowRef。
  void designerVersion.value
  return designerComponent.value
})

const panelKey = computed(() =>
  `${props.modelValue.id}:${props.modelValue.reportId}:v${
    props.modelValue.id === 'designer' ? designerVersion.value : 0
  }`,
)

function retryDesigner(): void {
  designerComponent.value = createDesignerPanel()
  designerVersion.value++
}

async function openFullscreen(event: MouseEvent): Promise<void> {
  fullscreenTrigger.value = event.currentTarget as HTMLButtonElement
  if (import.meta.env.DEV && !document.querySelector('#overlay-root')) {
    throw new Error('Missing #overlay-root for report fullscreen')
  }
  fullscreen.value = true
  await nextTick()
  document.querySelector<HTMLElement>('[data-fullscreen-close]')?.focus()
}

async function closeFullscreen(): Promise<void> {
  fullscreen.value = false
  await nextTick()
  fullscreenTrigger.value?.focus()
}
</script>

<template>
  <button type="button" @click="openFullscreen">全屏预览</button>

  <AsyncPanelBoundary @retry="retryDesigner">
    <KeepAlive :max="2">
      <component
        :is="panel"
        :key="panelKey"
        :report-id="modelValue.reportId"
      />
    </KeepAlive>
    <template #fallback><PanelSkeleton /></template>
  </AsyncPanelBoundary>

  <Teleport to="#overlay-root">
    <div
      v-if="fullscreen"
      role="dialog"
      aria-modal="true"
      aria-labelledby="fullscreen-title"
      @keydown.esc="closeFullscreen"
    >
      <h2 id="fullscreen-title">报表全屏预览</h2>
      <button data-fullscreen-close type="button" @click="closeFullscreen">
        关闭
      </button>
      <PreviewPanel :report-id="modelValue.reportId" />
    </div>
  </Teleport>
</template>
```

真实 dialog 还必须实现 Tab/Shift+Tab focus trap、背景滚动锁、嵌套 overlay 栈、背景 inert/aria 隔离；第 05 章会完整实现。这里只展示渲染边界。

### 6. 面板生命周期示例

```vue
<!-- RunsPanel.vue -->
<script setup lang="ts">
import { onActivated, onDeactivated, onUnmounted } from 'vue'
import { usePausablePolling } from './usePausablePolling'

const props = defineProps<{ reportId: string }>()
const { start, pause, dispose } = usePausablePolling(
  () => refreshRuns(props.reportId),
  5_000,
)

function onShortcut(event: KeyboardEvent): void {
  if (event.key === 'r' && (event.metaKey || event.ctrlKey)) {
    event.preventDefault()
    void refreshRuns(props.reportId)
  }
}

let listening = false
function addShortcut(): void {
  if (listening) return
  listening = true
  window.addEventListener('keydown', onShortcut)
  start()
}
function removeShortcut(): void {
  if (!listening) return
  listening = false
  window.removeEventListener('keydown', onShortcut)
  pause()
}

onActivated(addShortcut)
onDeactivated(removeShortcut)
onUnmounted(() => {
  removeShortcut()
  dispose()
})

addShortcut()

declare function refreshRuns(reportId: string): Promise<void>
</script>
```

### 7. 必测行为

```ts
it('does not duplicate polling across activations', async () => {
  vi.useFakeTimers()
  // mount host → 切换 tab 20 次 → 每次推进 5s
  // 断言活跃 RunsPanel 每周期只调用一次；停用期间为 0。
})

it('keeps local draft by business key and remounts after eviction', async () => {
  // 输入 designer 草稿 → 切 preview → 回 designer，草稿仍在；
  // 再依次让 3 个不同 key 进入 max=2 缓存，最旧 key 返回时实例 uid 改变。
})

it('shows delayed fallback and a recoverable terminal error', async () => {
  vi.useFakeTimers()
  // loader deferred；149ms 不显示 skeleton，150ms 显示；
  // 自动 retry 一次后 reject，role=alert 出现；点击 retry 创建新 wrapper。
})
```

Playwright 至少覆盖：点击全屏 → 焦点在关闭按钮 → Tab 不逃出 dialog（完整实现后）→ Escape → 焦点回原触发按钮。

### 8. 常见错解与生产限制

- 缓存 key 加了每次 render 变化的值：KeepAlive 永远命不中。
- 只写 `onUnmounted(clearInterval)`：deactivated 期间仍轮询。
- activated 每次 add 匿名 listener：无法 remove，叠加触发。
- 以为 Suspense fallback 会接住所有错误：pending 与 error 是两条通道。
- 无限 chunk retry：网络或部署故障时形成风暴。
- `max=20` 不经测量缓存编辑器：组件实例、文档模型、worker、DOM 可能占数百 MB。应记录实例内存、使用频率和恢复成本，考虑只保留序列化草稿，淘汰重型运行时。
- Teleport 后只测可见性，不测键盘和焦点：视觉正确但不可访问。

如果不用 Suspense，可让 `AsyncPanelBoundary` 拥有 `idle/loading/success/error` loader 状态与 150ms timer，成功后 render `shallowRef<Component>`。外部 slots、retry 事件、错误 UI 不变，这就是“把实验性能力隔离在边界内”。
