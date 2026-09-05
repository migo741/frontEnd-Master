# 第 03 章答案：状态证明与泛型组件契约

## 练习 1 参考答案：用户编辑状态机

### 1. 类型先表达业务事实

```ts
// user-editor.ts
export interface UserDto {
  id: string
  name: string
  email: string
  created_at: string
}

export interface User {
  id: string
  name: string
  email: string
  createdAt: Date
}

export interface UserDraft {
  name: string
  email: string
}

export type SaveError =
  | { kind: 'conflict'; message: string; serverVersion?: User }
  | { kind: 'network'; message: string }
  | { kind: 'validation'; message: string; fields: Readonly<Record<string, string>> }
  | { kind: 'unknown'; message: string }

export type UserEditorState =
  | { status: 'idle' }
  | { status: 'loading'; userId: string }
  | { status: 'not-found'; userId: string }
  | { status: 'forbidden'; userId: string }
  | { status: 'load-error'; userId: string; error: Error }
  | { status: 'ready-clean'; user: User }
  | { status: 'ready-dirty'; user: User; draft: UserDraft }
  | { status: 'ready-saving'; user: User; draft: UserDraft; requestId: string }
  | { status: 'ready-save-error'; user: User; draft: UserDraft; error: SaveError }

export type UserEditorEvent =
  | { type: 'LOAD'; userId: string }
  | { type: 'LOAD_OK'; user: User }
  | { type: 'LOAD_NOT_FOUND' }
  | { type: 'LOAD_FORBIDDEN' }
  | { type: 'LOAD_FAILED'; error: Error }
  | { type: 'EDIT'; patch: Partial<UserDraft> }
  | { type: 'DISCARD' }
  | { type: 'SAVE'; requestId: string }
  | { type: 'SAVE_OK'; requestId: string; user: User }
  | { type: 'SAVE_FAILED'; requestId: string; error: SaveError }
```

这里 `Partial<UserDraft>` 只用于 EDIT 的“补丁事件”，不作为持久状态；应用补丁后 state 中仍是完整 `UserDraft`。

### 2. 纯 reducer

```ts
function assertNever(value: never): never {
  throw new Error(`Unhandled variant: ${JSON.stringify(value)}`)
}

function draftOf(user: User): UserDraft {
  return { name: user.name, email: user.email }
}

function invalid(state: UserEditorState, event: UserEditorEvent): never {
  throw new Error(`Invalid transition: ${state.status} + ${event.type}`)
}

export function transition(
  state: UserEditorState,
  event: UserEditorEvent,
): UserEditorState {
  // 保存结果可能在用户继续编辑、切用户或离开后返回。它是已定义的 stale event，静默忽略。
  if (
    (event.type === 'SAVE_OK' || event.type === 'SAVE_FAILED')
    && state.status !== 'ready-saving'
  ) return state

  switch (state.status) {
    case 'idle': {
      if (event.type === 'LOAD') return { status: 'loading', userId: event.userId }
      return invalid(state, event)
    }

    case 'loading': {
      switch (event.type) {
        case 'LOAD': return { status: 'loading', userId: event.userId }
        case 'LOAD_OK': return { status: 'ready-clean', user: event.user }
        case 'LOAD_NOT_FOUND': return { status: 'not-found', userId: state.userId }
        case 'LOAD_FORBIDDEN': return { status: 'forbidden', userId: state.userId }
        case 'LOAD_FAILED': return {
          status: 'load-error', userId: state.userId, error: event.error,
        }
        default: return invalid(state, event)
      }
    }

    case 'not-found':
    case 'forbidden':
    case 'load-error': {
      if (event.type === 'LOAD') return { status: 'loading', userId: event.userId }
      return invalid(state, event)
    }

    case 'ready-clean': {
      switch (event.type) {
        case 'LOAD': return { status: 'loading', userId: event.userId }
        case 'EDIT': return {
          status: 'ready-dirty',
          user: state.user,
          draft: { ...draftOf(state.user), ...event.patch },
        }
        default: return invalid(state, event)
      }
    }

    case 'ready-dirty': {
      switch (event.type) {
        case 'EDIT': return {
          ...state,
          draft: { ...state.draft, ...event.patch },
        }
        case 'DISCARD': return { status: 'ready-clean', user: state.user }
        case 'SAVE': return {
          status: 'ready-saving',
          user: state.user,
          draft: state.draft,
          requestId: event.requestId,
        }
        case 'LOAD': return { status: 'loading', userId: event.userId }
        default: return invalid(state, event)
      }
    }

    case 'ready-saving': {
      switch (event.type) {
        case 'EDIT':
          // 离开 saving 状态即撤销旧 requestId 的提交权限。
          return {
            status: 'ready-dirty',
            user: state.user,
            draft: { ...state.draft, ...event.patch },
          }
        case 'SAVE_OK':
          return event.requestId === state.requestId
            ? { status: 'ready-clean', user: event.user }
            : state
        case 'SAVE_FAILED':
          return event.requestId === state.requestId
            ? {
                status: 'ready-save-error',
                user: state.user,
                draft: state.draft,
                error: event.error,
              }
            : state
        case 'LOAD': return { status: 'loading', userId: event.userId }
        default: return invalid(state, event)
      }
    }

    case 'ready-save-error': {
      switch (event.type) {
        case 'EDIT': return {
          status: 'ready-dirty',
          user: state.user,
          draft: { ...state.draft, ...event.patch },
        }
        case 'DISCARD': return { status: 'ready-clean', user: state.user }
        case 'SAVE': return {
          status: 'ready-saving',
          user: state.user,
          draft: state.draft,
          requestId: event.requestId,
        }
        case 'LOAD': return { status: 'loading', userId: event.userId }
        default: return invalid(state, event)
      }
    }

    default: return assertNever(state)
  }
}
```

`invalid` 的参数仍保留具体联合，因此开发期给出组合错误。stale save result 被单独定义为合法 no-op，解决“saving 中继续 EDIT”与迟到响应。

### 3. unknown 边界与 DTO 转换

```ts
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function requiredString(
  record: Record<string, unknown>,
  key: string,
): string {
  const value = record[key]
  if (typeof value !== 'string' || value.trim() === '') {
    throw new TypeError(`${key} must be a non-empty string`)
  }
  return value
}

export function parseUserDto(input: unknown): UserDto {
  if (!isRecord(input)) throw new TypeError('user payload must be an object')
  const dto: UserDto = {
    id: requiredString(input, 'id'),
    name: requiredString(input, 'name'),
    email: requiredString(input, 'email'),
    created_at: requiredString(input, 'created_at'),
  }
  if (!/^\S+@\S+\.\S+$/.test(dto.email)) throw new TypeError('email is invalid')
  if (Number.isNaN(Date.parse(dto.created_at))) {
    throw new TypeError('created_at must be an ISO-compatible date')
  }
  return dto
}

export function toUser(dto: UserDto): User {
  return {
    id: dto.id,
    name: dto.name,
    email: dto.email,
    createdAt: new Date(dto.created_at),
  }
}
```

生产项目优先 schema 库并共享服务端契约；手写校验适合展示边界，但邮箱/日期规则应由领域定义，示例正则不是完整 RFC 校验。

### 4. 代表性测试

```ts
import { describe, expect, it } from 'vitest'
import { parseUserDto, transition, type User, type UserEditorState } from './user-editor'

const user: User = {
  id: 'u1', name: 'Ada', email: 'ada@example.com', createdAt: new Date(0),
}

describe('user editor transition', () => {
  it('loads and edits into a complete draft', () => {
    let state: UserEditorState = { status: 'idle' }
    state = transition(state, { type: 'LOAD', userId: 'u1' })
    state = transition(state, { type: 'LOAD_OK', user })
    state = transition(state, { type: 'EDIT', patch: { name: 'Grace' } })
    expect(state).toMatchObject({
      status: 'ready-dirty', draft: { name: 'Grace', email: 'ada@example.com' },
    })
  })

  it('ignores an old save result after further editing', () => {
    let state: UserEditorState = {
      status: 'ready-dirty', user, draft: { name: 'Ada 2', email: user.email },
    }
    state = transition(state, { type: 'SAVE', requestId: 'r1' })
    state = transition(state, { type: 'EDIT', patch: { name: 'Ada 3' } })
    state = transition(state, {
      type: 'SAVE_OK', requestId: 'r1', user: { ...user, name: 'Ada 2' },
    })
    expect(state).toMatchObject({ status: 'ready-dirty', draft: { name: 'Ada 3' } })
  })

  it('ignores a mismatched request id while saving', () => {
    const state: UserEditorState = {
      status: 'ready-saving', user,
      draft: { name: user.name, email: user.email }, requestId: 'new',
    }
    expect(transition(state, {
      type: 'SAVE_OK', requestId: 'old', user,
    })).toBe(state)
  })

  it('distinguishes forbidden and not found', () => {
    const loading: UserEditorState = { status: 'loading', userId: 'u1' }
    expect(transition(loading, { type: 'LOAD_FORBIDDEN' }).status).toBe('forbidden')
    expect(transition(loading, { type: 'LOAD_NOT_FOUND' }).status).toBe('not-found')
  })

  it('rejects invalid transitions', () => {
    expect(() => transition({ status: 'idle' }, { type: 'DISCARD' }))
      .toThrow('Invalid transition')
  })
})

describe('parseUserDto', () => {
  it('accepts and converts a valid transport shape', () => {
    expect(parseUserDto({
      id: 'u1', name: 'Ada', email: 'ada@example.com', created_at: '2024-01-01',
    })).toMatchObject({ id: 'u1' })
  })

  it.each([
    null,
    {},
    { id: 'u1', name: 'Ada', email: 42, created_at: '2024-01-01' },
    { id: 'u1', name: 'Ada', email: 'bad', created_at: '2024-01-01' },
    { id: 'u1', name: 'Ada', email: 'a@b.com', created_at: 'not-date' },
  ])('rejects invalid external input: %j', payload => {
    expect(() => parseUserDto(payload)).toThrow()
  })
})
```

类型负例放在被 vue-tsc 检查的文件：

```ts
declare const loading: Extract<UserEditorState, { status: 'loading' }>
// @ts-expect-error loading 状态没有 draft
void loading.draft

declare const clean: Extract<UserEditorState, { status: 'ready-clean' }>
// @ts-expect-error clean 状态没有 error
void clean.error

// @ts-expect-error email 必须是 string
const badDraft: UserDraft = { name: 'Ada', email: 123 }

// @ts-expect-error SAVE 必须携带 requestId
const badEvent: UserEditorEvent = { type: 'SAVE' }
```

### 5. 常见错解

- state 里仍保留 `loading/saving/dirty` 多个 boolean，只给它们加字面量类型。
- 用 `Partial<User>` 当长期 draft，导致提交前到处非空断言。
- reducer 内调用 API/生成 requestId，破坏可重复测试。
- 只按 requestId 判断但 EDIT 后仍保留 saving 状态，旧成功覆盖新草稿。
- 把所有 HTTP 错误都变成 `message: string`，UI 无法决定冲突处理或重试。

---

## 练习 2 参考答案：泛型 `EntityPicker`

### 1. 内部上下文桥

运行时只有一个 Symbol，泛型会被擦除。把唯一的窄化桥封装在内部模块，禁止业务调用方自行指定错误 TKey：

```ts
// picker-context.ts（仅组件内部导入）
import { inject, provide, type InjectionKey, type Ref } from 'vue'

export interface PickerContext<TKey extends PropertyKey> {
  activeKey: Readonly<Ref<TKey | null>>
  selectedKey: Readonly<Ref<TKey | null>>
  activate(key: TKey): void
  select(key: TKey): void
}

const key: InjectionKey<PickerContext<PropertyKey>> = Symbol('EntityPicker')

export function providePickerContext<TKey extends PropertyKey>(
  context: PickerContext<TKey>,
): void {
  // 泛型 Ref 的可变性使直接赋值不安全；此桥由同一 root/option 组件族封闭维护。
  provide(key, context as unknown as PickerContext<PropertyKey>)
}

export function usePickerContext<TKey extends PropertyKey>(): PickerContext<TKey> {
  const context = inject(key)
  if (!context) throw new Error('Picker option must be used inside EntityPicker')
  return context as unknown as PickerContext<TKey>
}
```

若希望对外开放 compound components，更强的方案是 `createPicker<TKey>()` 工厂返回共享同一个 typed InjectionKey 的 Root/Option；不要把这个内部泛型 hook 暴露给任意消费者。

### 2. 核心 SFC

```vue
<!-- EntityPicker.vue -->
<script setup lang="ts" generic="TItem, TKey extends PropertyKey">
import {
  computed,
  readonly,
  ref,
  useId,
  useTemplateRef,
  watchEffect,
} from 'vue'
import { providePickerContext } from './picker-context'

const props = withDefaults(defineProps<{
  items: readonly TItem[]
  getKey: (item: TItem) => TKey
  getLabel: (item: TItem) => string
  disabled?: boolean
}>(), { disabled: false })

const model = defineModel<TKey | null>({ required: true })
const emit = defineEmits<{
  select: [item: TItem, key: TKey]
  clear: []
}>()
defineSlots<{
  option(props: {
    item: TItem
    key: TKey
    selected: boolean
    active: boolean
  }): unknown
  empty(props: { query: string }): unknown
}>()

const query = ref('')
const open = ref(false)
const activeKey = ref<TKey | null>(null)
const inputId = useId()
const listboxId = `${inputId}-listbox`
const input = useTemplateRef<HTMLInputElement>('input')

const normalizedQuery = computed(() => query.value.trim().toLocaleLowerCase())
const visibleItems = computed(() => {
  const needle = normalizedQuery.value
  if (!needle) return props.items
  return props.items.filter(item =>
    props.getLabel(item).toLocaleLowerCase().includes(needle),
  )
})

const visibleKeys = computed(() => visibleItems.value.map(props.getKey))
const selectedItemVisible = computed(() =>
  model.value === null
  || visibleKeys.value.some(key => Object.is(key, model.value)),
)

if (import.meta.env.DEV) {
  watchEffect(() => {
    const seen: TKey[] = []
    for (const item of props.items) {
      const itemKey = props.getKey(item)
      if (seen.some(key => Object.is(key, itemKey))) {
        throw new Error(`EntityPicker received duplicate key: ${String(itemKey)}`)
      }
      seen.push(itemKey)
    }
  })
}

function choose(item: TItem): void {
  if (props.disabled) return
  const key = props.getKey(item)
  model.value = key
  emit('select', item, key)
  open.value = false
}

function clear(): void {
  if (props.disabled || model.value === null) return
  model.value = null
  emit('clear')
}

function focus(): void {
  input.value?.focus()
}

providePickerContext<TKey>({
  activeKey: readonly(activeKey),
  selectedKey: readonly(model),
  activate: key => { activeKey.value = key },
  select: key => {
    const item = props.items.find(candidate => Object.is(props.getKey(candidate), key))
    if (item !== undefined) choose(item)
  },
})

defineExpose<{ focus(): void; clear(): void }>({ focus, clear })
</script>

<template>
  <div class="entity-picker">
    <label :for="inputId">选择项目</label>
    <input
      :id="inputId"
      ref="input"
      v-model="query"
      role="combobox"
      :disabled="disabled"
      :aria-expanded="open"
      :aria-controls="listboxId"
      @focus="open = true"
    >

    <p v-if="!selectedItemVisible" role="status">当前值不在筛选结果中</p>

    <ul v-if="open" :id="listboxId" role="listbox">
      <template v-if="visibleItems.length === 0">
        <li><slot name="empty" :query="query">无结果</slot></li>
      </template>
      <template v-else>
        <li
          v-for="item in visibleItems"
          :key="getKey(item)"
          role="option"
          :aria-selected="Object.is(getKey(item), model)"
          @mouseenter="activeKey = getKey(item)"
          @mousedown.prevent="choose(item)"
        >
          <slot
            name="option"
            v-bind="{
              item,
              key: getKey(item),
              selected: Object.is(getKey(item), model),
              active: Object.is(getKey(item), activeKey),
            }"
          >
            {{ getLabel(item) }}
          </slot>
        </li>
      </template>
    </ul>
  </div>
</template>
```

注意：`defineModel` 返回的 `model` ref 在模板中自动解包。完整 Combobox 的键盘、焦点、IME 与 `aria-activedescendant` 会在第 05 章补齐，本题不应把这个最小结构误称为完全可访问。

### 3. 调用处类型关系

```vue
<script setup lang="ts">
import { ref } from 'vue'
import EntityPicker from './EntityPicker.vue'

interface User { id: string; name: string; email: string }
const users: readonly User[] = [
  { id: 'u1', name: 'Ada', email: 'ada@example.com' },
]
const selectedUserId = ref<string | null>(null)

function audit(email: string, id: string): void {
  console.log({ email, id })
}
</script>

<template>
  <EntityPicker
    v-model="selectedUserId"
    :items="users"
    :get-key="user => user.id"
    :get-label="user => user.name"
    @select="(user, id) => audit(user.email, id)"
  >
    <template #option="{ item }">{{ item.email }}</template>
  </EntityPicker>
</template>
```

### 4. 行为与类型验收

```ts
it('does not clear an invisible selected model', async () => {
  const wrapper = mount(EntityPicker, {
    props: {
      items: [{ id: 'u1', name: 'Ada' }],
      getKey: (item: { id: string }) => item.id,
      getLabel: (item: { name: string }) => item.name,
      modelValue: 'missing',
      'onUpdate:modelValue': vi.fn(),
    },
  })
  await wrapper.get('input').setValue('Ada')
  expect(wrapper.text()).toContain('当前值不在筛选结果中')
  expect(wrapper.emitted('update:modelValue')).toBeUndefined()
})

it('honors disabled when imperative clear is called', () => {
  const wrapper = mount(EntityPicker, {
    props: {
      items: [], getKey: String, getLabel: String,
      modelValue: 'x', disabled: true,
    },
  })
  ;(wrapper.vm as unknown as { clear(): void }).clear()
  expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  expect(wrapper.emitted('clear')).toBeUndefined()
})
```

泛型 SFC 的负例最好放进 `.vue` fixture 由 `vue-tsc` 跑：错误 model 类型、slot 访问不存在字段、select handler 参数错误均应失败。仅用普通 `tsc` 不能充分验证模板推断。

### 5. 生产限制与常见错解

- 把 `selectedItem = ref(props...)` 再 watch 双向同步：制造双份真相和时序问题。
- 过滤后自动清 model：组件擅自做领域决策，远程分页时尤其危险。
- 允许对象作 key：对象身份跨序列化/重取数据不稳定；primitive key 更适合 VNode、URL 和缓存。
- 用 `as any` 跨过泛型 context：错误会渗透整个组件族；把不可避免的类型擦除桥封在一处并测试。
- 对 10,000 items deep watch：输入数组应作为不可变集合替换，过滤 computed 只读必要字段；更大规模还需虚拟化/服务端搜索。
- expose `open/query/activeKey/model`：父组件能破坏内部不变量。只留 focus/clear 命令。

最终复盘：类型安全的价值不在于“零断言”。真正高级的做法是把不可避免的运行时/泛型擦除桥缩到一个可审计模块，其余业务代码保持可推导、可穷尽、可验证。
