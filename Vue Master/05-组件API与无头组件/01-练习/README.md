# 第 05 章练习：Combobox 状态机与生产级 Dialog

## 练习 1：实现与 DOM 无关的 Combobox 状态机（机制题）

### 契约

```ts
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

export interface TransitionResult<TKey extends PropertyKey> {
  state: ComboboxState<TKey>
  effects: readonly (
    | { type: 'COMMIT'; key: TKey }
    | { type: 'SCROLL_ACTIVE_INTO_VIEW'; key: TKey }
  )[]
}

export declare function transition<TKey extends PropertyKey>(
  state: ComboboxState<TKey>,
  event: ComboboxEvent<TKey>,
): TransitionResult<TKey>
```

### 规则

1. active/selected 用 key，不用 index；key 用 `Object.is`。
2. INPUT 更新 query 并打开；不得隐式改变 selected。
3. ARROW 打开列表，从当前 active 向方向移动，循环且跳 disabled；无可用项时 active=null。
4. ENTER 在 composing 时无动作；否则仅 active 指向当前可用项才产生 COMMIT 并关闭。
5. OPTIONS_CHANGED：active 仍存在且 enabled 则保留，否则选择第一个 enabled；空列表为 null。
6. ESCAPE 只关闭并清 active，不清 selected；BLUR 关闭。
7. COMPOSITION_START 后 Enter 不提交；COMPOSITION_END 同步最终 query，但不自动提交。
8. EXTERNAL_VALUE 更新 selected，不复制 label/query；受控父值是最终真相。
9. 输入含重复 key 时抛 `DuplicateOptionKeyError`；纯 reducer 不操作 DOM。

### 验收

- 过滤前 active=B，过滤后 B 消失，修复到第一个 enabled。
- `[A disabled, B, C disabled, D]` 正反循环只经过 B/D。
- composing Enter 无 effect；composition end 后显式 Enter 才 commit。
- external value 在 options 不可见时仍保留 selected。
- 至少 15 个 table-driven tests；再写 2 个 property/invariant test：active 要么 null，要么是 enabled option；每次 ENTER 最多一个 COMMIT。

### 发散

- 若产品不希望 Arrow 循环，哪个规则需要成为配置？
- 异步结果乱序应由状态机处理，还是数据 composable 处理？为什么？

---

## 练习 2：实现可嵌套的 Headless Dialog（生产题）

### 公共契约

```ts
export type CloseReason =
  | 'escape'
  | 'backdrop'
  | 'close-button'
  | 'programmatic'

// HeadlessDialog.vue
// model: open:boolean，required
// props:
//   initialFocus?: () => HTMLElement | null
//   closeOnEscape?: boolean（默认 true）
//   closeOnBackdrop?: boolean（默认 true）
//   teleportTo?: string（默认 '#overlay-root'）
// emits:
//   close: [reason: CloseReason]
// default slot:
//   { close(reason?: CloseReason), titleId, descriptionId }
```

### 必须行为

1. open 后 Teleport 到目标，panel 为 `role=dialog`、`aria-modal=true`，由稳定 titleId/descriptionId 关联；目标不存在时开发期抛明确错误。
2. 保存打开前 activeElement。nextTick 后优先 initialFocus，其次首个可聚焦元素，否则 panel。
3. Tab/Shift+Tab 在 panel 内循环；动态 disabled/新增元素下一次按键即时生效。
4. 只有 stack 顶层响应 Escape、focus containment、backdrop；关闭子层不得解锁父层背景。
5. backdrop 仅 `target===currentTarget` 才关闭；panel 点击不关闭。
6. 每次关闭 emit 一次 reason 并请求 `open=false`；父拒绝更新时组件仍视为 open，不擅自卸载。
7. 真正从 open→closed 后恢复触发焦点；触发元素已移除时回到最近父 dialog panel 或显式 fallback，不 focus body。
8. 第一个 dialog 打开时锁 body scroll、让 app root inert；最后一个关闭才恢复原值。dispose/异常路径也必须释放。
9. nested、KeepAlive deactivate、组件 unmount、快速 open→close→open 均不得泄漏 document listener/锁。
10. reduced motion 时不得强制等待动画；SSR 首次不得读取 document/window。

### 可访问性与错误边界

- 默认 slot 必须渲染带 `:id="titleId"` 的可见标题；开发期若缺关联元素给 warning。
- Escape 关闭若业务有 dirty guard，应由受控父层拒绝或确认，不在 primitive 丢数据。
- 锁/inert 恢复时保留打开前原始值，不粗暴写 false/空字符串。

### 验收与交付

- `dialog-stack.ts`、`useFocusTrap.ts`、`HeadlessDialog.vue`、使用示例。
- Vitest/VTU：model/close reason、backdrop、topmost、引用计数、unmount cleanup。
- Playwright：初始焦点、正反 Tab、Escape 只关顶层、关闭恢复、背景不可交互；加 axe 扫描但不把它当唯一验收。
- 手工检查：VoiceOver 或 NVDA 能读出 dialog 名称，焦点不逃逸。

### 发散

- 原生 `<dialog>` 能减少哪些工作？它的浏览器/样式/嵌套策略还需验证什么？
- 为什么业务团队通常应该优先成熟 headless library，而不是复制这份教学实现？
