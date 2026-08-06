# 第 04 章练习

## 练习一：安全的用户更新协议

实体：

```ts
type User = {
  readonly id: string
  readonly createdAt: Date
  email: string
  displayName: string
  avatarUrl: string | null
  roles: readonly ('member' | 'admin')[]
  preferences: {theme: 'light' | 'dark'; locale: string}
}
```

任务：

- 普通用户只能改 displayName/avatar/preferences.theme；管理员可另改 roles；id/createdAt/email 均禁止。
- 缺失=不改；avatarUrl null=清除；禁止用 undefined 清除。
- preferences 更新是字段级，不替换整个对象。
- 分别设计 UserSelfPatch/AdminPatch，不使用 `DeepPartial<User>`。
- 实现 `applySelfPatch(user, patch)` 纯函数，readonly 输入/新对象输出。
- 写 `@ts-expect-error` 负例和运行时测试。

## 练习二：配置合并器（高难）

三层配置：defaults < file < environment。要求：

- 只允许 schema 中定义的 key；不接受 `__proto__/constructor/prototype`。
- 数组是替换，不是拼接；普通对象递归 merge；Date/Map 不允许出现在配置输入。
- `undefined` 表示层中未提供；`null` 只有 schema 明确允许才是值。
- 返回深 readonly 的规范配置；默认值应用一次。
- 类型 Merge 与运行时行为一致；给出 recursion depth/循环引用策略。

先写运行时规范，再写类型。禁止直接 `Object.assign(defaults, input)` 和通用无限 `DeepMerge<A,B>`。

