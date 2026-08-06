# 第 07 章练习

## 练习一：嵌套表单错误映射

模型：

```ts
type ProfileForm = {
  name: string
  address: {city: string; zip: string}
  tags: string[]
}
```

任务：

- 设计仅针对本表单域的 `FieldErrors<T>`：叶子是 string[]；对象递归；数组有整体错误和按 index 项错误。
- optional 字段的 error 是否 optional，语义写清。
- 不递归 Date/File/Map/Function；这些作为叶子。
- 实现 `flattenErrors` 生成 `{path,message}`，静态 path 与运行时一致。
- 限制递归深度或限定 FormValue 域，避免通用 Deep 类型。
- 写类型正负例与运行时 flatten 测试。

## 练习二：权限安全投影（高难）

```ts
type Document = {
  id: string
  title: string
  body: string
  ownerId: string
  internalScore: number
  secretToken: string
}
```

定义角色可见 key registry，要求：

- registry 的 key 必须覆盖 guest/member/admin，字段只能来自 Document。
- `project(doc, 'guest')` 返回只包含 guest 字段的精确类型。
- runtime 必须真正构造新对象，不只 Pick 类型。
- 新增敏感字段时默认不可见；新增角色时编译失败直到配置。
- symbol/原型/额外字段不会泄漏；测试 JSON bytes。

比较 allowlist 与 omit denylist，解释安全上为何选择 allowlist。

