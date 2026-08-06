# 第 02 章参考答案

## 练习一：核心类型

用显式 `selected: T | null` 避免 `undefined` 的双重含义：

```tsx
type LoadStatus =
  | {kind: 'idle'; message?: never; retry?: never}
  | {kind: 'loading'; message?: never; retry?: never}
  | {kind: 'ready'; message?: never; retry?: never}
  | {kind: 'error'; message: string; retry: () => void}

type BaseProps<T> = {
  label: string
  items: readonly T[]
  getKey: (item: T) => React.Key
  getLabel: (item: T) => string
  status: LoadStatus
}

type Controlled<T> = {
  mode: 'controlled'
  value: T | null
  defaultValue?: never
  onValueChange: (value: T | null) => void
}

type Uncontrolled<T> = {
  mode?: 'uncontrolled'
  value?: never
  defaultValue?: T | null
  onValueChange?: (value: T | null) => void
}

type AsyncSelectProps<T> = BaseProps<T> & (Controlled<T> | Uncontrolled<T>)
```

显式 `mode` 比用 `'value' in props` 稍啰嗦，但彻底消除了“受控且 value 为 undefined”的歧义，公共库中值得。

最小实现可用原生 `select` 获得较好的基础语义：

```tsx
export function AsyncSelect<T>(props: AsyncSelectProps<T>) {
  const [inner, setInner] = useState<T | null>(props.defaultValue ?? null)
  const selected = props.mode === 'controlled' ? props.value : inner

  function change(next: T | null) {
    if (props.mode !== 'controlled') setInner(next)
    props.onValueChange?.(next)
  }

  if (props.status.kind === 'error') {
    return (
      <div role="alert">
        {props.status.message}
        <button onClick={props.status.retry}>重试</button>
      </div>
    )
  }

  const selectedKey = selected == null ? '' : String(props.getKey(selected))

  return (
    <label>
      {props.label}
      <select
        disabled={props.status.kind === 'loading'}
        value={selectedKey}
        onChange={event => {
          const next = props.items.find(
            item => String(props.getKey(item)) === event.target.value,
          ) ?? null
          change(next)
        }}
      >
        <option value="">未选择</option>
        {props.items.map(item => (
          <option key={props.getKey(item)} value={String(props.getKey(item))}>
            {props.getLabel(item)}
          </option>
        ))}
      </select>
      {props.status.kind === 'loading' && <span role="status">加载中</span>}
    </label>
  )
}
```

真实组件要处理 key 字符串碰撞，最好让 `getValue` 明确返回 string，而不是偷偷 stringify 任意 key。

类型测试：

```tsx
const users = [{id: '1', name: 'Ada'}]
<AsyncSelect label="用户" items={users} getKey={x => x.id} getLabel={x => x.name}
  mode="controlled" value={users[0]} onValueChange={() => {}} status={{kind: 'ready'}} />

// @ts-expect-error error 状态必须提供 retry
const badStatus: LoadStatus = {kind: 'error', message: '失败'}

// @ts-expect-error 受控模式不得传 defaultValue
<AsyncSelect label="用户" items={users} getKey={x => x.id} getLabel={x => x.name}
  mode="controlled" value={null} defaultValue={users[0]}
  onValueChange={() => {}} status={{kind: 'ready'}} />
```

## 练习二：设计要点

Context 只保存 open、setOpen、triggerRef、contentId 等 family 状态。消费 hook 统一报错：

```tsx
function useModalContext() {
  const value = useContext(ModalContext)
  if (!value) throw new Error('Modal components must be used inside <Modal.Root>')
  return value
}
```

组合事件时尊重使用者取消：

```tsx
function composeEventHandlers<E extends {defaultPrevented: boolean}>(
  user: ((event: E) => void) | undefined,
  internal: (event: E) => void,
) {
  return (event: E) => {
    user?.(event)
    if (!event.defaultPrevented) internal(event)
  }
}
```

Root 仍应采用判别联合。Trigger 最好渲染真实 `button type="button"`；若支持 `asChild`，必须验证恰好一个元素并保留语义。Content 挂载时保存此前焦点并聚焦标题/首个可交互元素，卸载时恢复 trigger；Escape 关闭。完整实现还要处理焦点圈、嵌套弹层、背景 inert、滚动锁、触屏和屏幕阅读器差异，所以生产应使用 Radix/React Aria 等成熟 primitive，并在其上构建品牌 API。

## 验收问题

1. `ReactNode` 包含字符串、数组、null 等，不能保证能 `cloneElement`；需 `ReactElement` 加运行时校验。
2. 业务上通常只关心新值。暴露 DOM event 会把元素类型、事件生命周期和测试方式泄漏到上层。
3. 当语义集合有限、ref 类型复杂、允许任意元素会破坏无障碍，或团队无法承担类型维护时，不做通用 `as`。

