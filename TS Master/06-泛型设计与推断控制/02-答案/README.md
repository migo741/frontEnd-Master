# 第 06 章参考答案

## 练习一

关键是把列定义成 mapped union，让 key 每个变体保持关联：

```ts
type StringKey<T> = Extract<keyof T, string>

type ColumnFor<T> = {
  [K in StringKey<T>]: {
    key: K
    header: string
    render?: (value: T[K], row: T) => string
    sort?: (a: T[K], b: T[K]) => number
  }
}[StringKey<T>]

function defineColumns<T>() {
  return <const C extends readonly ColumnFor<T>[]>(columns: C) => columns
}
```

调用端每项由 `key` 判别并上下文推断 render。实现表格时：

```ts
function renderCell<T>(row: T, column: ColumnFor<T>): string {
  const value = row[column.key]
  // union of callbacks 与 value 关联在泛型实现中可能难以调用。
  return column.render ? callColumnRenderer(row, column) : String(value)
}
```

可把执行封装进列创建时生成的闭包，避免异构数组取出后丢相关性：

```ts
function column<T, K extends StringKey<T>>(def: Column<T,K>) {
  return {...def, renderRow: (row:T) => def.render?.(row[def.key], row) ?? String(row[def.key])}
}
```

这是类型设计与运行时表示共同调整，比在最终循环 `as never` 更可维护。对象字段是否默认可排序无法仅凭 T[K] 可靠判断运行时，应要求显式 sort 或受控 primitive key helper。

## 练习二

可用状态标记：

```ts
type Missing = {readonly __state: 'missing'}
type Present = {readonly __state: 'present'}

class RouteBuilder<M = Missing, P = Missing, H = Missing> {
  method(method: HttpMethod): RouteBuilder<Present, P, H> { /* 返回新 builder */ }
  path<const Path extends string>(path: Path): RouteBuilder<M, Present, H> { /* ... */ }
  handler(handler: Handler): RouteBuilder<M, P, Present> { /* ... */ }
  build(this: RouteBuilder<Present, Present, Present>): Route { /* runtime 再检查 */ }
}
```

实现内部最好存一个普通 PartialRuntimeState 并在每步创建新 builder，局部构造断言封装。若 path/schema 推断加入后公开签名迅速膨胀，推荐 `defineRoute({method,path,schema,handler})` 一个对象：判别/上下文类型同样强，错误更集中，声明更小。

步骤 builder 仅在顺序本身有用户价值、步骤很多且 IDE 引导明显时值得。HTTP route 的“字段齐全”通常一个对象 + `satisfies` 更好；把 build 前置条件运行时验证还能支持动态配置。高级答案可以选择不做 builder，并用消费者体验/声明大小证明。

