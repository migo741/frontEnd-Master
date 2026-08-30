# 答案与复盘

## 题 1

```ts
type RemoteData<T> =
  | { status: 'idle' }
  | { status: 'loading'; previous?: T }
  | { status: 'success'; data: T }
  | { status: 'error'; error: string; previous?: T }
```

模板按 `state.status` 分支，成功分支才能访问 `data`，错误分支必有 `error`。刷新时进入 `{ status: 'loading', previous: oldData }`，既表达 loading，也明确旧数据只是 previous。相比三个 ref，这个模型阻止“不 loading 却无 data 无 error”等无意义组合。

可加入穷尽函数：

```ts
function assertNever(value: never): never {
  throw new Error(`Unhandled state: ${JSON.stringify(value)}`)
}
```

## 题 2

严格到“每一列 formatter 精确对应各自 key”需要分布式联合：

```ts
type Column<T> = {
  [K in keyof T]-?: {
    key: K
    title: string
    format?: (value: T[K], row: T) => string
  }
}[keyof T]

type Props<T> = {
  rows: readonly T[]
  rowKey: (row: T) => string
  columns: readonly Column<T>[]
}
```

组件：

```vue
<script setup lang="ts" generic="T">
defineProps<Props<T>>()
defineEmits<{ select: [row: T] }>()
defineSlots<{ cell(props: { row: T; column: Column<T> }): unknown }>()
</script>
```

使用侧用 `as const satisfies readonly Column<User>[]`，既校验键又保留字面量。工程上可把高度动态的渲染交给 slot，避免在通用组件内部用复杂断言。类型的目标是提升调用体验，不是追求零断言；若 Vue 模板泛型边界迫使内部出现一个局部、被测试覆盖的断言，比把 `any` 泄漏给所有调用方更可控。

