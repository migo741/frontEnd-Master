# 第 04 章参考答案

## 练习一

公共 DTO 显式 allowlist：

```ts
type UserSelfPatch = {
  displayName?: string
  avatarUrl?: string | null
  preferences?: {theme?: User['preferences']['theme']}
}

type AdminPatch = UserSelfPatch & {
  roles?: readonly ('member' | 'admin')[]
}

function applySelfPatch(user: Readonly<User>, patch: UserSelfPatch): User {
  return {
    ...user,
    ...(patch.displayName !== undefined ? {displayName: patch.displayName} : {}),
    ...('avatarUrl' in patch ? {avatarUrl: patch.avatarUrl} : {}),
    preferences: {
      ...user.preferences,
      ...(patch.preferences?.theme !== undefined
        ? {theme: patch.preferences.theme}
        : {}),
    },
  }
}
```

在 `exactOptionalPropertyTypes` 下 `{avatarUrl: undefined}` 不合法。用 `'avatarUrl' in patch` 表达存在；其值类型已是 string|null。真实边界仍需 Schema strip/reject id/roles 等未知字段，TS 只约束已编译调用者。

`AdminPatch = UserSelfPatch & {...}` 这里字段不冲突；若角色更新有审批/审计，应该是独立命令而非 Patch。

## 练习二

通用配置 merge 最可靠是 schema 驱动：schema 节点明确 object/array/scalar/nullable/default，解析每层 unknown 并拒绝未知/危险 key，再按节点规则合并。返回类型从 schema 推导，避免另写 DeepMerge。

伪接口：

```ts
type ConfigSchema<T> = {
  parseLayer(value: unknown): PartialLayer<T>
  merge(base: T, layer: PartialLayer<T>): T
  readonly(value: T): DeepReadonlyKnown<T>
}
```

原型污染防御不能只靠类型：只接受 plain object（prototype 为 Object.prototype/null）、用 `Object.hasOwn`、key allowlist、创建 null-prototype 中间字典，不赋值危险 key。限制深度/节点数，检测 WeakSet 循环；JSON 输入本身无循环，但编程式 config 可能有。

不要承诺任意 T 的深 readonly/merge。配置 schema 的已知类型只包含 JSON-like 值，可安全定义针对该域的递归类型；运行时若 freeze，明确深 freeze 成本。数组整体 replace 与对象逐字段 merge 用测试锁定。

