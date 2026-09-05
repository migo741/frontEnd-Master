# 第 05 章答案：Combobox 状态机与生产级 Dialog

## 练习 1 参考答案：Combobox 状态机

### 1. 为什么 reducer 返回 effects

纯状态机不应调用 `scrollIntoView` 或 emit。它只描述“需要提交/滚动”，适配层决定何时操作 DOM：

```text
keydown → transition(state, event)
        ├─ next state → Vue reactive state
        └─ effects
            ├─ COMMIT → model update + emit select
            └─ SCROLL_ACTIVE_INTO_VIEW → nextTick 后找 option DOM
```

这样键盘规则可在 Node 单测，不依赖 jsdom 布局。

### 2. 完整 reducer

```ts
// combobox-machine.ts
export interface Option<TKey extends PropertyKey> {
  key: TKey
  disabled: boolean
}

export interface ComboboxState<TKey extends PropertyKey> {
  open: boolean
  query: string
  selectedKey: TKey | null
  activeKey: TKey | null
  composing: boolean
}

export type ComboboxEvent<TKey extends PropertyKey> =
  | { type: 'INPUT'; value: string }
  | { type: 'OPTIONS_CHANGED'; options: readonly Option<TKey>[] }
  | { type: 'ARROW'; direction: 1 | -1; options: readonly Option<TKey>[] }
  | { type: 'ENTER'; options: readonly Option<TKey>[] }
  | { type: 'ESCAPE' }
  | { type: 'BLUR' }
  | { type: 'COMPOSITION_START' }
  | { type: 'COMPOSITION_END'; value: string }
  | { type: 'EXTERNAL_VALUE'; key: TKey | null }

export type ComboboxEffect<TKey extends PropertyKey> =
  | { type: 'COMMIT'; key: TKey }
  | { type: 'SCROLL_ACTIVE_INTO_VIEW'; key: TKey }

export interface TransitionResult<TKey extends PropertyKey> {
  state: ComboboxState<TKey>
  effects: readonly ComboboxEffect<TKey>[]
}

export class DuplicateOptionKeyError extends Error {
  constructor(readonly key: PropertyKey) {
    super(`Duplicate combobox option key: ${String(key)}`)
    this.name = 'DuplicateOptionKeyError'
  }
}

function assertUnique<TKey extends PropertyKey>(
  options: readonly Option<TKey>[],
): void {
  const keys: TKey[] = []
  for (const option of options) {
    if (keys.some(key => Object.is(key, option.key))) {
      throw new DuplicateOptionKeyError(option.key)
    }
    keys.push(option.key)
  }
}

function enabled<TKey extends PropertyKey>(
  options: readonly Option<TKey>[],
): readonly Option<TKey>[] {
  assertUnique(options)
  return options.filter(option => !option.disabled)
}

function findByKey<TKey extends PropertyKey>(
  options: readonly Option<TKey>[],
  key: TKey | null,
): Option<TKey> | undefined {
  if (key === null) return undefined
  return options.find(option => Object.is(option.key, key))
}

function move<TKey extends PropertyKey>(
  currentKey: TKey | null,
  direction: 1 | -1,
  options: readonly Option<TKey>[],
): TKey | null {
  const candidates = enabled(options)
  if (candidates.length === 0) return null
  const currentIndex = candidates.findIndex(option => Object.is(option.key, currentKey))
  if (currentIndex < 0) {
    return direction === 1 ? candidates[0]!.key : candidates.at(-1)!.key
  }
  const nextIndex = (currentIndex + direction + candidates.length) % candidates.length
  return candidates[nextIndex]!.key
}

export function transition<TKey extends PropertyKey>(
  state: ComboboxState<TKey>,
  event: ComboboxEvent<TKey>,
): TransitionResult<TKey> {
  switch (event.type) {
    case 'INPUT':
      return {
        state: { ...state, query: event.value, open: true },
        effects: [],
      }

    case 'OPTIONS_CHANGED': {
      const candidates = enabled(event.options)
      const current = findByKey(event.options, state.activeKey)
      const activeKey = current && !current.disabled
        ? current.key
        : candidates[0]?.key ?? null
      return {
        state: { ...state, activeKey },
        effects: activeKey === null
          ? []
          : [{ type: 'SCROLL_ACTIVE_INTO_VIEW', key: activeKey }],
      }
    }

    case 'ARROW': {
      const activeKey = move(state.activeKey, event.direction, event.options)
      return {
        state: { ...state, open: true, activeKey },
        effects: activeKey === null
          ? []
          : [{ type: 'SCROLL_ACTIVE_INTO_VIEW', key: activeKey }],
      }
    }

    case 'ENTER': {
      assertUnique(event.options)
      if (state.composing || !state.open) return { state, effects: [] }
      const active = findByKey(event.options, state.activeKey)
      if (!active || active.disabled) return { state, effects: [] }
      return {
        state: {
          ...state,
          selectedKey: active.key,
          activeKey: null,
          open: false,
        },
        effects: [{ type: 'COMMIT', key: active.key }],
      }
    }

    case 'ESCAPE':
      return {
        state: { ...state, open: false, activeKey: null },
        effects: [],
      }

    case 'BLUR':
      return {
        state: { ...state, open: false, activeKey: null },
        effects: [],
      }

    case 'COMPOSITION_START':
      return { state: { ...state, composing: true }, effects: [] }

    case 'COMPOSITION_END':
      return {
        state: { ...state, composing: false, query: event.value, open: true },
        effects: [],
      }

    case 'EXTERNAL_VALUE':
      return {
        state: { ...state, selectedKey: event.key },
        effects: [],
      }
  }
}
```

这里没有 default，是为了让 TypeScript 在新增 event 后提示函数缺少返回；也可加 `assertNever(event)`。

### 3. 表驱动测试与不变量

```ts
import { describe, expect, it } from 'vitest'
import { transition, type ComboboxState, type Option } from './combobox-machine'

const options = [
  { key: 'A', disabled: true },
  { key: 'B', disabled: false },
  { key: 'C', disabled: true },
  { key: 'D', disabled: false },
] as const satisfies readonly Option<string>[]

const initial: ComboboxState<string> = {
  open: false,
  query: '',
  selectedKey: null,
  activeKey: null,
  composing: false,
}

describe('combobox machine', () => {
  it.each([
    { start: null, direction: 1 as const, expected: 'B' },
    { start: null, direction: -1 as const, expected: 'D' },
    { start: 'B', direction: 1 as const, expected: 'D' },
    { start: 'D', direction: 1 as const, expected: 'B' },
    { start: 'B', direction: -1 as const, expected: 'D' },
  ])('moves enabled options: $start/$direction → $expected', row => {
    const result = transition(
      { ...initial, open: true, activeKey: row.start },
      { type: 'ARROW', direction: row.direction, options },
    )
    expect(result.state.activeKey).toBe(row.expected)
  })

  it('repairs an active key removed by filtering', () => {
    const result = transition(
      { ...initial, open: true, activeKey: 'B' },
      { type: 'OPTIONS_CHANGED', options: [{ key: 'D', disabled: false }] },
    )
    expect(result.state.activeKey).toBe('D')
  })

  it('does not commit Enter during IME composition', () => {
    const result = transition(
      { ...initial, open: true, composing: true, activeKey: 'B' },
      { type: 'ENTER', options },
    )
    expect(result.effects).toEqual([])
    expect(result.state.selectedKey).toBeNull()
  })

  it('commits only after composition ends and a new Enter arrives', () => {
    const composing = { ...initial, open: true, composing: true, activeKey: 'B' }
    const ended = transition(composing, {
      type: 'COMPOSITION_END', value: '北京',
    }).state
    const result = transition(ended, { type: 'ENTER', options })
    expect(result.effects).toEqual([{ type: 'COMMIT', key: 'B' }])
  })

  it('keeps an external selected key even when not visible', () => {
    const result = transition(initial, { type: 'EXTERNAL_VALUE', key: 'REMOTE' })
    expect(result.state.selectedKey).toBe('REMOTE')
  })

  it('rejects duplicate keys', () => {
    expect(() => transition(initial, {
      type: 'OPTIONS_CHANGED',
      options: [{ key: 'A', disabled: false }, { key: 'A', disabled: false }],
    })).toThrow('Duplicate combobox option key')
  })

  it('always leaves active null or enabled after option repair', () => {
    const samples: readonly (readonly Option<string>[])[] = [
      [],
      [{ key: 'A', disabled: true }],
      options,
      [{ key: 'X', disabled: false }],
    ]
    for (const candidateOptions of samples) {
      const state = transition(
        { ...initial, activeKey: 'MISSING' },
        { type: 'OPTIONS_CHANGED', options: candidateOptions },
      ).state
      const active = candidateOptions.find(option => Object.is(option.key, state.activeKey))
      expect(state.activeKey === null || active?.disabled === false).toBe(true)
    }
  })

  it('emits at most one commit for every Enter', () => {
    for (const activeKey of [null, 'A', 'B', 'D'] as const) {
      const result = transition(
        { ...initial, open: true, activeKey },
        { type: 'ENTER', options },
      )
      expect(result.effects.filter(effect => effect.type === 'COMMIT').length)
        .toBeLessThanOrEqual(1)
    }
  })
})
```

### 4. 适配到 Vue 时的边界

- reducer 内 `selectedKey` 是“期望的下一状态”；受控组件真正提交后仍以父 model 为准。适配层 emit 后用 `EXTERNAL_VALUE` 同步父值。
- 异步乱序由数据 composable 的 latest-wins 处理；状态机只消费当前有效 options，职责更单一。
- `SCROLL_ACTIVE_INTO_VIEW` 应 `await nextTick()`，确认相应 option 已虚拟化渲染，再滚动。
- 循环行为可以作为 reducer config；不要在每个 key handler 散落 if。
- reducer 正确不等于 ARIA 正确；组件层仍要稳定 id、aria-activedescendant、焦点和 live 状态。

---

## 练习 2 参考答案：可嵌套 Headless Dialog

> 以下是可运行的核心教学实现，重点展示 stack、锁、焦点和受控关闭。真正发布组件库前仍应处理 Shadow DOM、多个 app root、移动端 viewport、动画离场和更广浏览器/辅助技术矩阵；优先评估成熟库。

### 1. 全局 overlay 栈与环境锁

```ts
// dialog-stack.ts
export interface DialogRecord {
  id: string
  panel(): HTMLElement | null
}

const stack: DialogRecord[] = []
let originalBodyOverflow: string | null = null
let appRoot: HTMLElement | null = null
let originalAppInert: boolean | null = null

function lockEnvironment(): void {
  if (typeof document === 'undefined' || stack.length !== 1) return
  originalBodyOverflow = document.body.style.overflow
  document.body.style.overflow = 'hidden'

  appRoot = document.querySelector<HTMLElement>('#app')
  if (appRoot) {
    originalAppInert = appRoot.inert
    appRoot.inert = true
  }
}

function unlockEnvironment(): void {
  if (typeof document === 'undefined' || stack.length !== 0) return
  if (originalBodyOverflow !== null) {
    document.body.style.overflow = originalBodyOverflow
  }
  if (appRoot && originalAppInert !== null) appRoot.inert = originalAppInert
  originalBodyOverflow = null
  originalAppInert = null
  appRoot = null
}

export function pushDialog(record: DialogRecord): void {
  if (stack.some(item => item.id === record.id)) return
  stack.push(record)
  lockEnvironment()
}

export function removeDialog(id: string): void {
  const index = stack.findIndex(item => item.id === id)
  if (index < 0) return
  stack.splice(index, 1)
  unlockEnvironment()
}

export function isTopDialog(id: string): boolean {
  return stack.at(-1)?.id === id
}

export function topDialogPanel(): HTMLElement | null {
  return stack.at(-1)?.panel() ?? null
}

export function dialogCountForTests(): number {
  return stack.length
}
```

锁保存原值而不是关闭时粗暴写空；stack 长度就是引用计数。组件异常卸载也必须调用 remove。

### 2. 焦点工具

```ts
// useFocusTrap.ts
const focusableSelector = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
  '[contenteditable="true"]',
].join(',')

function isAvailable(element: HTMLElement): boolean {
  return !element.hidden
    && element.getAttribute('aria-hidden') !== 'true'
    && !element.closest('[inert]')
}

export function focusables(panel: HTMLElement): HTMLElement[] {
  return [...panel.querySelectorAll<HTMLElement>(focusableSelector)]
    .filter(isAvailable)
}

export function focusInside(
  panel: HTMLElement,
  preferred?: () => HTMLElement | null,
): void {
  const candidate = preferred?.()
  if (candidate && panel.contains(candidate) && isAvailable(candidate)) {
    candidate.focus()
    return
  }
  ;(focusables(panel)[0] ?? panel).focus()
}

export function trapTab(panel: HTMLElement, event: KeyboardEvent): void {
  if (event.key !== 'Tab') return
  const items = focusables(panel)
  if (items.length === 0) {
    event.preventDefault()
    panel.focus()
    return
  }

  const first = items[0]!
  const last = items.at(-1)!
  const active = document.activeElement
  if (event.shiftKey && (active === first || !panel.contains(active))) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && (active === last || !panel.contains(active))) {
    event.preventDefault()
    first.focus()
  }
}
```

每次 keydown 重新查询，能适应动态 disabled/新增节点。可见性判断的跨浏览器细节很多，生产库通常有更成熟的 tabbable 算法。

### 3. `HeadlessDialog.vue`

```vue
<script setup lang="ts">
import {
  nextTick,
  onActivated,
  onBeforeUnmount,
  onDeactivated,
  ref,
  useAttrs,
  useId,
  useTemplateRef,
  watch,
} from 'vue'
import {
  isTopDialog,
  pushDialog,
  removeDialog,
  topDialogPanel,
} from './dialog-stack'
import { focusInside, trapTab } from './useFocusTrap'

defineOptions({ inheritAttrs: false })

export type CloseReason =
  | 'escape'
  | 'backdrop'
  | 'close-button'
  | 'programmatic'

const props = withDefaults(defineProps<{
  initialFocus?: () => HTMLElement | null
  closeOnEscape?: boolean
  closeOnBackdrop?: boolean
  teleportTo?: string
}>(), {
  closeOnEscape: true,
  closeOnBackdrop: true,
  teleportTo: '#overlay-root',
})

const open = defineModel<boolean>('open', { required: true })
const emit = defineEmits<{ close: [reason: CloseReason] }>()
defineSlots<{
  default(props: {
    close: (reason?: CloseReason) => void
    titleId: string
    descriptionId: string
  }): unknown
}>()

const attrs = useAttrs()
const instanceId = useId()
const titleId = `${instanceId}-title`
const descriptionId = `${instanceId}-description`
const panel = useTemplateRef<HTMLElement>('panel')
const activeSession = ref(false)
let openGeneration = 0
let restoreTarget: HTMLElement | null = null

function requestClose(reason: CloseReason = 'programmatic'): void {
  if (!open.value || !isTopDialog(instanceId)) return
  emit('close', reason)
  open.value = false
  // 如果父组件拒绝更新，open getter 仍为 true，DOM 和 session 保持。
}

function onDocumentKeydown(event: KeyboardEvent): void {
  if (!isTopDialog(instanceId)) return
  const element = panel.value
  if (!element) return
  if (event.key === 'Escape' && props.closeOnEscape) {
    event.preventDefault()
    event.stopPropagation()
    requestClose('escape')
    return
  }
  trapTab(element, event)
}

function onDocumentFocusIn(event: FocusEvent): void {
  if (!isTopDialog(instanceId)) return
  const element = panel.value
  const target = event.target
  if (element && target instanceof Node && !element.contains(target)) {
    focusInside(element, props.initialFocus)
  }
}

function restoreFocus(): void {
  const candidate = restoreTarget
  restoreTarget = null
  void nextTick().then(() => {
    if (candidate?.isConnected) {
      candidate.focus()
      return
    }
    // 嵌套子层触发元素消失时，回到仍打开的父 panel，而非 body。
    topDialogPanel()?.focus()
  })
}

function stopSession(shouldRestore: boolean): void {
  if (!activeSession.value) return
  activeSession.value = false
  document.removeEventListener('keydown', onDocumentKeydown, true)
  document.removeEventListener('focusin', onDocumentFocusIn, true)
  removeDialog(instanceId)
  if (shouldRestore) restoreFocus()
}

async function startSession(): Promise<void> {
  if (typeof document === 'undefined' || activeSession.value || !open.value) return
  const generation = ++openGeneration
  restoreTarget = document.activeElement instanceof HTMLElement
    ? document.activeElement
    : null

  if (import.meta.env.DEV && !document.querySelector(props.teleportTo)) {
    throw new Error(`HeadlessDialog teleport target not found: ${props.teleportTo}`)
  }

  await nextTick()
  if (generation !== openGeneration || !open.value || !panel.value) return

  activeSession.value = true
  pushDialog({ id: instanceId, panel: () => panel.value })
  document.addEventListener('keydown', onDocumentKeydown, true)
  document.addEventListener('focusin', onDocumentFocusIn, true)
  focusInside(panel.value, props.initialFocus)

  if (import.meta.env.DEV) {
    const title = document.getElementById(titleId)
    const description = document.getElementById(descriptionId)
    if (!title || !panel.value.contains(title)) {
      console.warn(`HeadlessDialog requires a visible title with id="${titleId}"`)
    }
    if (!description || !panel.value.contains(description)) {
      console.warn(`HeadlessDialog description id "${descriptionId}" is not rendered`)
    }
  }
}

function onBackdrop(event: MouseEvent): void {
  if (
    props.closeOnBackdrop
    && isTopDialog(instanceId)
    && event.target === event.currentTarget
  ) requestClose('backdrop')
}

watch(open, isOpen => {
  openGeneration++
  if (isOpen) void startSession()
  else stopSession(true)
}, { immediate: true, flush: 'post' })

onDeactivated(() => {
  openGeneration++
  stopSession(false)
})
onActivated(() => {
  if (open.value) void startSession()
})
onBeforeUnmount(() => {
  openGeneration++
  stopSession(false)
})
</script>

<template>
  <Teleport :to="teleportTo">
    <div
      v-if="open"
      class="dialog-backdrop"
      data-dialog-backdrop
      @mousedown="onBackdrop"
    >
      <section
        ref="panel"
        v-bind="attrs"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="titleId"
        :aria-describedby="descriptionId"
        tabindex="-1"
        data-dialog-panel
      >
        <slot
          :close="requestClose"
          :title-id="titleId"
          :description-id="descriptionId"
        />
      </section>
    </div>
  </Teleport>
</template>
```

说明：`attrs` 明确落到 dialog panel，调用方的 class/data 属性不会落到 backdrop。组件仍强制覆盖关键 role/aria-modal；公共库还应过滤调用方试图破坏的 tabindex/role 契约。

### 4. 使用示例

```vue
<script setup lang="ts">
import { ref } from 'vue'
import HeadlessDialog, { type CloseReason } from './HeadlessDialog.vue'

const open = ref(false)
const deleteInput = ref<HTMLInputElement | null>(null)
const dirty = ref(false)

function handleClose(reason: CloseReason): void {
  if (dirty.value && !window.confirm('放弃未保存内容？')) {
    // 受控父层可以在收到 update 后立即保持/恢复 open；更完善的 API 可改成 close-request，
    // 由父确认后才更新 model，避免瞬态关闭。
    open.value = true
    return
  }
  open.value = false
}
</script>

<template>
  <button type="button" @click="open = true">删除项目</button>
  <HeadlessDialog
    :open="open"
    :initial-focus="() => deleteInput"
    @update:open="value => { if (value) open = true }"
    @close="handleClose"
  >
    <template #default="{ close, titleId, descriptionId }">
      <h2 :id="titleId">删除项目</h2>
      <p :id="descriptionId">此操作不可撤销，请输入项目名确认。</p>
      <input ref="deleteInput" aria-label="项目名">
      <button type="button" @click="close('close-button')">取消</button>
      <button type="button">确认删除</button>
    </template>
  </HeadlessDialog>
</template>
```

这个示例特意展示“close request 与受控决策”的摩擦：更成熟的设计会提供可取消 `beforeClose` 或独立 `close-request`，确认后由父层设置 open=false，避免先 emit update 再拒绝。primitive 不能自行丢弃 dirty 数据。

### 5. 代表性组件测试

```ts
import { mount } from '@vue/test-utils'
import { h, nextTick, ref } from 'vue'
import { afterEach, expect, it } from 'vitest'
import HeadlessDialog from './HeadlessDialog.vue'
import { dialogCountForTests } from './dialog-stack'

afterEach(() => {
  document.body.innerHTML = ''
})

function installRoots(): void {
  document.body.innerHTML = '<div id="app"></div><div id="overlay-root"></div>'
}

it('emits exactly one escape close reason from the top dialog', async () => {
  installRoots()
  const open = ref(true)
  const wrapper = mount(HeadlessDialog, {
    attachTo: '#app',
    props: {
      open: open.value,
      'onUpdate:open': value => { open.value = value },
    },
    slots: {
      default: ({ titleId, descriptionId }) => [
        h('h2', { id: titleId }, 'Title'),
        h('p', { id: descriptionId }, 'Description'),
        h('button', 'Close'),
      ],
    },
  })
  await nextTick()
  document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
  expect(wrapper.emitted('close')).toEqual([['escape']])
  await wrapper.unmount()
})

it('does not treat panel click as backdrop click', async () => {
  installRoots()
  const wrapper = mount(HeadlessDialog, {
    attachTo: '#app',
    props: { open: true },
    slots: { default: '<h2 id="x">Title</h2>' },
  })
  await nextTick()
  document.querySelector<HTMLElement>('[data-dialog-panel]')?.click()
  expect(wrapper.emitted('close')).toBeUndefined()
  document.querySelector<HTMLElement>('[data-dialog-backdrop]')?.dispatchEvent(
    new MouseEvent('mousedown', { bubbles: true }),
  )
  expect(wrapper.emitted('close')).toEqual([['backdrop']])
  wrapper.unmount()
})

it('restores environment only after the last nested dialog closes', async () => {
  installRoots()
  const first = mount(HeadlessDialog, {
    attachTo: '#app', props: { open: true }, slots: { default: 'first' },
  })
  const second = mount(HeadlessDialog, {
    attachTo: '#app', props: { open: true }, slots: { default: 'second' },
  })
  await nextTick()
  expect(dialogCountForTests()).toBe(2)
  expect(document.body.style.overflow).toBe('hidden')

  second.unmount()
  expect(dialogCountForTests()).toBe(1)
  expect(document.body.style.overflow).toBe('hidden')
  first.unmount()
  expect(dialogCountForTests()).toBe(0)
  expect(document.body.style.overflow).toBe('')
})
```

实际项目应封装 mount factory 自动提供合法 title/description，避免每个用例被开发 warning 淹没。还要测试父拒绝 close、rapid reopen、deactivate、Teleport target 缺失和 listener 计数。

### 6. Playwright 关键流程

```ts
test('nested dialogs keep focus and restore it', async ({ page }) => {
  await page.getByRole('button', { name: '打开父弹窗' }).click()
  await expect(page.getByRole('dialog', { name: '父弹窗' })).toBeVisible()
  await page.getByRole('button', { name: '打开子弹窗' }).click()
  await expect(page.getByRole('dialog', { name: '子弹窗' })).toBeVisible()

  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog', { name: '子弹窗' })).toBeHidden()
  await expect(page.getByRole('dialog', { name: '父弹窗' })).toBeVisible()
  await expect(page.getByRole('button', { name: '打开子弹窗' })).toBeFocused()

  // 在父 dialog 内循环 Tab/Shift+Tab，断言 activeElement 不进入 #app 背景。
})
```

axe 扫描补充 role/name/关系问题；人工 VoiceOver/NVDA 验证打开时宣布标题、描述，Tab 顺序自然，关闭后上下文正确。

### 7. 教学实现仍需审查的生产边界

- `#app`/`#overlay-root` 是单应用假设；多 app、Shadow DOM、iframe 需要注入 environment/root manager。
- `inert` 兼容性及 polyfill、iOS body scroll lock、滚动条宽度补偿需支持矩阵。
- CSS transition 离场会让“model false”和“DOM 真正移除”分时；锁与焦点恢复应绑定存在阶段，而不是盲等固定毫秒。
- focusable 算法需处理 fieldset disabled、radio group、details、shadow roots、visibility、negative tabindex；成熟库更可靠。
- `aria-describedby` 应只在 description 实际存在时设置；可由 `DialogDescription` compound component注册，而非开发期 query 猜测。
- 原生 `<dialog>.showModal()` 自带 top layer、一定的 focus/modal 行为，值得优先评估；仍需验证样式、嵌套、关闭事件、SSR 和目标浏览器。
- 全局 module stack 在 HMR/微前端中要有宿主级生命周期和唯一实例，避免重复包各自认为自己 topmost。

### 8. 常见错解

- 每个 dialog 都无条件处理 Escape：一次关闭所有嵌套层。
- 关闭任意层就恢复 body overflow：父层仍开却背景可滚。
- focusables 只在 mounted 缓存一次：动态 disabled/表单字段变化后 trap 错。
- 点击判断只看事件冒泡：点 panel 也关闭。
- close 内直接 `open=false` 并卸载，不给受控父 dirty guard 决策。
- 用随机数生成 title id：SSR hydration 不一致。
- Teleport 后按 feature DOM 祖先找焦点：查询边界错误。
- “axe 通过”就宣布无障碍完成：键盘时序和读屏上下文仍可能坏。

最后请用键盘亲自完成两遍：一次单层 Dialog，一次嵌套；再用中文输入法验证 Combobox 的 Enter。高级组件工程的底线是行为证据，不是 API 看起来优雅。
