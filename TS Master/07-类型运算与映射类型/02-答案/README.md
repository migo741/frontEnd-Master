# 第 07 章参考答案

## 练习一

先限定可支持值域，避免“任意 T 深递归”：

```ts
type Leaf = string | number | boolean | null | Date | File
type ArrayErrors<T> = {self?: string[]; items?: Partial<Record<number, FieldErrors<T>>>}

type FieldErrors<T> =
  T extends Leaf ? string[] :
  T extends readonly (infer U)[] ? ArrayErrors<U> :
  T extends object ? {[K in keyof T]?: FieldErrors<NonNullable<T[K]>>} :
  string[]
```

这是条件类型提前出现，下一章解释分布。生产可把 Date/File 叶子做可配置参数。错误对象属性 optional 表示“该字段无错误”；叶数组至少一条可用 non-empty tuple，但可能增加操作成本。

静态 path 的无限精确计算容易拖慢 checker。实际表单可用受限深度（如 5 层）或让 Schema issue path 是 `(string|number)[]`，在边界安全格式化。类型只需保证 error 树形状，没必要证明每个拼接字符串。

## 练习二

```ts
type Role = 'guest' | 'member' | 'admin'

const visible = {
  guest: ['id', 'title'],
  member: ['id', 'title', 'body', 'ownerId'],
  admin: ['id', 'title', 'body', 'ownerId', 'internalScore'],
} as const satisfies Record<Role, readonly (keyof Document)[]>

type VisibleKeys<R extends Role> = (typeof visible)[R][number]
type Projected<R extends Role> = Pick<Document, VisibleKeys<R>>

function project<R extends Role>(doc: Document, role: R): Projected<R> {
  const output: Partial<Document> = Object.create(null)
  for (const key of visible[role]) {
    // key 与 output 的相关写入在泛型索引下关联较难，局部 helper 封装
    assignKey(output, doc, key)
  }
  return output as Projected<R>
}
```

```ts
function assignKey<K extends keyof Document>(out: Partial<Document>, src: Document, key: K) {
  ;(out as {[P in K]?: Document[P]})[key] = src[key]
}
```

断言只在构建完成边界，allowlist 由 `satisfies` 检查并有 JSON 测试。更高安全可用每角色 Schema `.pick` 直接 parse/strip。

allowlist 在新增 secret 字段时默认不导出；denylist 新字段会默认泄漏。角色完整 Record 保证新增角色需配置。输出 null-prototype/显式 JSON DTO，且只枚举静态 keys，不复制 getters/原型/symbol。

