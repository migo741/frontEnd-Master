# 第 08 章参考答案

## 练习一

核心提取可分段：

```ts
type SegmentParam<S extends string> =
  S extends `:${infer P}?` ? {[K in P]?: string} :
  S extends `:${infer P}` ? {[K in P]: string} :
  S extends `*${infer P}` ? {[K in P]: string[]} :
  {}

type MergeParams<A, B> = Omit<A, keyof B> & B

type RouteParams<Path extends string> =
  string extends Path ? Record<string, string | string[] | undefined> :
  Path extends `${infer Head}/${infer Tail}`
    ? MergeParams<SegmentParam<Head>, RouteParams<Tail>>
    : SegmentParam<Path>
```

此版重名 key 由后者覆盖，类型不拒绝；runtime parser 必须拒绝。要在类型层收集 Seen/返回错误品牌会显著增加复杂度，公共 API 可用 `defineRoute` 在运行时启动时验证，并让测试保证静态/运行规则一致。

联合 Path 裸参数会分布，可得到 params 联合；回调要先按具体 route 判别，否则无法安全访问成员特有 key。若希望把 union 当整体，包 tuple，但通常 route 定义是单字面量。

## 练习二

```ts
type Primitive = string | number | boolean | bigint | symbol | null | undefined
type Prev = [never, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

type DeepReadonlyJson<T, D extends number = 5> =
  D extends 0 ? T :
  T extends Primitive ? T :
  T extends readonly [/* tuple detection below */ ...infer U]
    ? {readonly [K in keyof T]: DeepReadonlyJson<T[K], Prev[D]>} :
  T extends readonly (infer U)[] ? readonly DeepReadonlyJson<U, Prev[D]>[] :
  T extends Record<string, unknown>
    ? {readonly [K in keyof T]: DeepReadonlyJson<T[K], Prev[D]>} :
  T
```

Tuple 检测更稳可用 `number extends T['length']` 区分数组/tuple。上面展开只示意，需在练习版本用测试校准 readonly tuple。

对 any 可先 `type IsAny<T> = 0 extends (1 & T) ? true : false`，选择返回 unknown/any；公共 API 更建议输入域从 Schema 已保证 JSON type，不为 any 加十层魔法。never 自然分布为 never；unknown 落到叶返回 unknown。

停止深度返回 T 保留剩余已知结构但不深只读；返回 unknown 更严格却损失可用性。文档说明。业务函数接受 readonly 浅视图通常足以防直接顶层写，深层不可变应由领域数据结构/运行时纪律保证；Deep 类型增加声明/IDE 成本且仍不 runtime freeze。

