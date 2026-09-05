# 第 13 章答案：从状态机到演进治理

## 题 1 参考答案：Async Combobox

### 1. 四个状态不能混成一个字符串

```ts
type LoadState =
  | { type: 'idle' }
  | { type: 'loading'; generation: number }
  | { type: 'success' }
  | { type: 'empty' }
  | { type: 'error'; message: string }

interface ComboboxState<T> {
  open: boolean
  query: string
  committed: T | null
  activeId: string | null
  options: readonly T[]
  load: LoadState
  composing: boolean
}
```

`query` 是用户正在编辑的文本，`committed` 是表单值，`activeId` 只是键盘预览。方向键不能改变 committed；Enter 才提交。Escape 关闭并把 query 恢复为 committed label。blur 的策略需明确：这里选择不自动提交 active，只关闭并恢复，避免用户仅 Tab 导航就改值。

transition 摘要：

| 当前 | 事件 | 新状态/动作 |
| --- | --- | --- |
| closed | input/ArrowDown | open；搜索或激活首个 enabled |
| open | ArrowDown/Up | active 移到下/上一个 enabled，循环策略显式定义 |
| open | Home/End | 首/末 enabled |
| open | Enter 且非 composing | commit active，emit，关闭 |
| open | Escape | 关闭，query 恢复 committed label |
| 任意 | query change | generation++，debounce，取消旧请求 |
| loading | 新结果且 generation 当前 | success/empty；修正 active |
| 任意 | external model update | committed/query 同步；不得 emit 回环 |

### 2. Public API

```ts
export interface ComboboxItem {
  id: string
  label: string
  disabled?: boolean
}

export interface AsyncComboboxProps<T extends ComboboxItem> {
  modelValue: string | null       // 提交 primitive id
  defaultValue?: string | null    // 仅在非受控版本采用；建议分组件或明确优先级
  loadOptions: (query: string, signal: AbortSignal) => Promise<readonly T[]>
  debounceMs?: number
  disabled?: boolean
  required?: boolean
  name?: string
  inputId?: string               // 未传时使用 SSR-safe id provider
}

export interface AsyncComboboxEmits {
  (event: 'update:modelValue', id: string | null): void
  (event: 'change', detail: { id: string | null; reason: 'select' | 'clear' }): void
  (event: 'open-change', open: boolean): void
}
```

身份只认 `item.id`，不认对象引用。这里建议 design system 对外坚持 controlled `modelValue`；若支持 uncontrolled，则 `modelValue !== undefined` 时外部为真相，`defaultValue` 只读一次，开发期警告两者同时传入。slot 可暴露 `{ item, active, selected, disabled }`，但不暴露可变内部 ref。

label、id、事件时序、slot props、ARIA/焦点行为与稳定 style hook 都是兼容边界。

### 3. Headless 核心实现

```ts
import {
  computed,
  nextTick,
  onBeforeUnmount,
  ref,
  shallowRef,
  watch,
  type ComputedRef,
  type Ref,
} from 'vue'

interface Item { id: string; label: string; disabled?: boolean }

// 不依赖浏览器 API，两端得到相同结果；实际库也可用统一的 SSR id provider。
function stableDomPart(value: string): string {
  return Array.from(value, (char) => char.codePointAt(0)!.toString(36)).join('-')
}

export function useAsyncCombobox<T extends Item>(options: {
  modelValue: Ref<string | null>
  load: (query: string, signal: AbortSignal) => Promise<readonly T[]>
  emitValue: (id: string | null) => void
  inputId: string
  listboxId: string
  debounceMs: number
}) {
  const open = ref(false)
  const query = ref('')
  const items = shallowRef<readonly T[]>([])
  const activeId = ref<string | null>(null)
  const status = ref<'idle' | 'loading' | 'success' | 'empty' | 'error'>('idle')
  const composing = ref(false)
  let timer: ReturnType<typeof setTimeout> | undefined
  let aborter: AbortController | undefined
  let generation = 0

  const enabled = computed(() => items.value.filter((item) => !item.disabled))
  const activeIndex = computed(() =>
    enabled.value.findIndex((item) => item.id === activeId.value),
  )
  const activeDomId: ComputedRef<string | undefined> = computed(() =>
    activeId.value ? optionDomId(activeId.value) : undefined,
  )

  function optionDomId(id: string): string {
    return `${options.listboxId}-option-${stableDomPart(id)}`
  }

  function normalizeActive(): void {
    if (enabled.value.some((item) => item.id === activeId.value)) return
    activeId.value = enabled.value[0]?.id ?? null
  }

  async function runSearch(own: number, signal: AbortSignal): Promise<void> {
    try {
      const result = await options.load(query.value, signal)
      if (own !== generation || signal.aborted) return
      items.value = result
      status.value = result.length ? 'success' : 'empty'
      normalizeActive()
    } catch (error: unknown) {
      if (own !== generation || signal.aborted) return
      status.value = 'error'
    }
  }

  function scheduleSearch(): void {
    generation += 1
    const own = generation
    aborter?.abort()
    aborter = new AbortController()
    if (timer !== undefined) clearTimeout(timer)
    status.value = 'loading'
    timer = setTimeout(() => void runSearch(own, aborter!.signal), options.debounceMs)
  }

  function move(delta: 1 | -1): void {
    if (!enabled.value.length) return
    const current = activeIndex.value
    const next = current < 0
      ? delta === 1 ? 0 : enabled.value.length - 1
      : (current + delta + enabled.value.length) % enabled.value.length
    activeId.value = enabled.value[next]?.id ?? null
  }

  function commitActive(): void {
    const item = enabled.value.find((candidate) => candidate.id === activeId.value)
    if (!item) return
    options.emitValue(item.id)
    query.value = item.label
    open.value = false
  }

  function onKeydown(event: KeyboardEvent): void {
    if (event.isComposing || composing.value) return
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      open.value = true
      move(event.key === 'ArrowDown' ? 1 : -1)
    } else if (event.key === 'Home' && open.value) {
      event.preventDefault(); activeId.value = enabled.value[0]?.id ?? null
    } else if (event.key === 'End' && open.value) {
      event.preventDefault(); activeId.value = enabled.value.at(-1)?.id ?? null
    } else if (event.key === 'Enter' && open.value) {
      event.preventDefault(); commitActive()
    } else if (event.key === 'Escape' && open.value) {
      event.preventDefault(); open.value = false
      const selected = items.value.find((item) => item.id === options.modelValue.value)
      query.value = selected?.label ?? ''
    }
  }

  watch(query, () => {
    if (!composing.value) scheduleSearch()
  })
  watch(items, () => void nextTick(normalizeActive))

  onBeforeUnmount(() => {
    generation += 1
    aborter?.abort()
    if (timer !== undefined) clearTimeout(timer)
  })

  return {
    open, query, items, activeId, activeDomId, status, composing,
    onKeydown, commitActive, scheduleSearch, optionDomId,
    inputProps: computed(() => ({
      id: options.inputId,
      role: 'combobox' as const,
      'aria-autocomplete': 'list' as const,
      'aria-expanded': open.value,
      'aria-controls': options.listboxId,
      'aria-activedescendant': open.value ? activeDomId.value : undefined,
    })),
  }
}
```

如果 option id 很长，生产库可为本次结果建立 id → 本地序号映射，但映射在 SSR 与客户端必须一致。`Array.prototype.at` 需要相应 TS lib；老目标可用索引。

### 4. Styled template 与 overlay

```vue
<template>
  <div ref="anchor" class="ds-combobox">
    <input
      v-bind="inputProps"
      v-model="query"
      @keydown="onKeydown"
      @focus="open = true"
      @compositionstart="composing = true"
      @compositionend="composing = false; scheduleSearch()"
    >
    <Teleport to="body">
      <div v-if="open" :style="floatingStyle" data-overlay="combobox">
        <ul :id="listboxId" role="listbox">
          <li
            v-for="item in items"
            :id="optionDomId(item.id)"
            :key="item.id"
            role="option"
            :aria-selected="item.id === modelValue"
            :aria-disabled="item.disabled || undefined"
            @pointerdown.prevent
            @click="!item.disabled && select(item)"
          >
            <slot name="option" :item="item" :active="item.id === activeId">
              {{ item.label }}
            </slot>
          </li>
        </ul>
        <p v-if="status === 'loading'" role="status">正在搜索…</p>
        <button v-if="status === 'error'" type="button" @click="retry">重试</button>
      </div>
    </Teleport>
  </div>
</template>
```

真实实现应使用可靠 positioning primitive 处理 anchor rect、flip/shift/resize/scroll；OverlayManager 以 stack 判断 Escape 和 outside pointer。`pointerdown.prevent` 防止点击 option 前 input blur。应避免在每次键入时 live announce 全部 loading；可 debounce announcement，只报告“有 N 项/失败”。

### 5. 测试矩阵

至少包括：

1. ArrowDown 跳过 disabled；
2. Home/End 到首末 enabled；
3. Enter 只提交 active id，方向键不改 committed；
4. Escape 恢复 committed label；
5. Tab 按协议关闭但不提交；
6. composition 期间 Enter 不提交、请求不乱发；
7. A 慢 B 快时 A 不覆盖 B；abort 后不进入 error；
8. 外部更新 `modelValue` 同步，不产生 emit 回环；
9. role/name/expanded/controls/activedescendant 指向存在节点；
10. Dialog 内 Teleport 不裁剪，Escape 只关闭 combobox 或顶层协议指定项；
11. browser 中焦点一直在 input，点击项后焦点策略正确；
12. SSR HTML 与 hydrate id 相同、零 mismatch；
13. unmount 清 timer/request/outside listener；
14. 真实读屏 + 中文 IME + 触屏冒烟测试。

100 条通常无需虚拟化，简单 DOM 更可靠。若变 10,000 本地项，要加窗口化、overscan、active item 自动滚入、aria row/index 策略、浏览器查找/读屏降级和 filter CPU 测量；更可能的产品答案是远程分页而非在 popup 放一万项。

### 6. Creatable 变化

value 需成为判别联合，例如 `{ type:'option'; id } | { type:'custom'; text }`，避免自定义文本与真实 id 混淆。Enter 在有 active option 时选 option，无 active 且 query 合法时创建；UI/读屏明确宣布“创建 X”。Escape 恢复已 committed 值；提交前做长度、重复、权限和服务端校验。它是 API breaking change，不能偷偷把 id string 改成任意文本。

## 题 2 参考答案：DataGrid + Token v2

### 1. 先切产品边界

v2 第一阶段支持服务端排序/过滤/分页、稳定行选择、只读表格与少量可编辑列；第二阶段再做列虚拟化、固定列、复杂 spreadsheet 导航。设计系统只定义交互与渲染协议，query 的业务权限/字段策略由 feature adapter 提供。

依赖方向：业务 feature → DataGrid styled/pattern → grid headless reducer → focus/virtualization primitive → token。DataGrid 不导入业务 store/API。

### 2. 核心 API

```ts
export interface GridColumn<Row> {
  id: string
  header: string
  width?: number
  sortable?: boolean
  value: (row: Row) => unknown
  editable?: boolean
}

export interface GridQuery {
  page: number
  pageSize: number
  sort: readonly { columnId: string; direction: 'asc' | 'desc' }[]
  filters: Readonly<Record<string, unknown>>
}

export interface DataGridProps<Row> {
  rows: readonly Row[]
  rowCount: number
  rowKey: (row: Row) => string
  columns: readonly GridColumn<Row>[]
  query: GridQuery
  selectedKeys: ReadonlySet<string>
  loading?: boolean
}

export interface GridEvents {
  (event: 'update:query', query: GridQuery): void
  (event: 'update:selectedKeys', keys: ReadonlySet<string>): void
  (event: 'edit-commit', change: {
    rowKey: string; columnId: string; value: unknown; baseVersion: string
  }): void
}
```

行身份来自业务稳定 key，选择跨页存 key，不存对象引用/数组下标。focus 和 editing 是不同判别状态；远端 response 带 request generation，旧页不能覆盖新 query。slot 暴露 typed `{ row, value, rowKey }`，并提供正式 class/part hook，减少 deep selector。

### 3. 100,000 行架构

```text
GridQuery
 → validated server endpoint
 → indexed sort/filter + cursor/page
 → { rows, total/hasNext, queryVersion }
 → current page/window
 → stable row keys + selection set
```

若每页 50–200 行，原生 `<table>` + 服务端分页通常比虚拟化更可访问、可打印。若业务要求连续滚动，则采用服务端游标 + 有上限 page cache + 行虚拟化；只在 DOM 中保留窗口，仍不能把所有数据一次下载。

只读 grid 优先 table；真正 spreadsheet 交互才使用 `role=grid`、roving tabindex、Arrow 二维移动、Enter/F2 编辑、Escape 取消、focus cell 滚入视口。提供分页/打印/导出通道；导出由服务端按当前 query 和权限生成，不从客户端已加载窗口拼装。

### 4. Token 迁移

```css
:root {
  --ds-primitive-blue-600: #2563eb;
  --ds-color-action-primary: var(--ds-primitive-blue-600);
  --ds-button-primary-background: var(--ds-color-action-primary);

  /* deprecated: remove in v3; lint + build warning */
  --blue-600: var(--ds-color-action-primary);
}
```

时间线：

1. v1.x 增加新 semantic token 与旧 alias，文档标 deprecated；
2. lint 禁止新增旧 token，codemod 替换已知用途；无法判断语义的地方人工审查；
3. 统计仓库/消费者使用，canary 截图四主题与关键业务；
4. v2 保留 alias（若既有承诺如此），给 dev/build warning；
5. 公布至少一个约定周期与 migration guide；
6. 下个 major v3 删除，并用 release note + consumer build 证明影响可控。

原始 `blue-600` 可能被用于文字、背景、border，不可机械全部映射 action primary；codemod 必须标记歧义。

### 5. v1 → v2 演进

- 建 adapter `LegacyDataTable` 把 v1 props 映射到 v2 子集；开发期警告 index key、对象引用选择和 deep selector。
- 选择 2–3 个代表消费者（简单表、服务端表、可编辑表）作为 contract fixtures。
- canary tag 只给试点；对比事件时序、键盘、SSR、截图和 bundle。
- 新业务只能用 v2；旧业务按风险/收益批次迁移。
- v2 breaking 点写 RFC、迁移表和 codemod，主版本发布；功能 flag 可回到 v1 adapter。
- 遥测只记录组件版本/已使用 feature，不采行数据；监控 render error、交互失败、性能和回滚率。

核心业务依赖未公开 selector 时，不永久冻结全部 DOM。短期提供正式 `part`/class hook 或 slot 并让旧 selector 有一段迁移窗口；若该 DOM 本就是公开承诺则兼容到 major。ADR 写消费者数量、迁移成本、可替代 hook、维护年限和删除日期。

### 6. 测试矩阵

| 层 | 证明 | 不能证明 |
| --- | --- | --- |
| reducer/state unit | query、selection、focus/edit transition | 真实 DOM focus/布局 |
| component interaction | role、事件、loading/empty/error、受控协议 | 浏览器滚动/读屏细节 |
| browser E2E | focus、键盘、虚拟滚动、编辑、IME | 所有辅助技术组合 |
| a11y manual/automation | 常见规则、读屏任务可完成 | 业务语义绝对正确 |
| visual regression | 主题/密度/viewport 的视觉变化 | 键盘与 ARIA 正确 |
| SSR/hydration | stable id/DOM、无 mismatch | 生产缓存安全 |
| consumer contract | 典型业务 build/runtime 兼容 | 未纳入样本的私有 hack |
| performance budget | DOM、更新数、scroll/input 指标 | 功能/语义正确性 |

视觉矩阵至少覆盖 light/dark/high-contrast、compact/default、loading/empty/error/selected/editing、窄/宽 viewport。固定字体、时间、动画与数据；每次 baseline 更新必须链接变更原因和 reviewer。

## 复写检查

合上答案后应能重写：

1. Combobox 四状态与键盘 transition；
2. active-descendant、异步 generation + abort、IME 生命周期；
3. DataGrid 稳定 row key、query、selection、focus/edit 模型；
4. 100,000 行的服务端边界与无障碍降级；
5. token alias → lint/codemod → canary → major 删除路径；
6. 各测试层“能证明/不能证明”的边界。
