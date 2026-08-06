# 第 01 章练习

## 练习一：编译通过，运行崩溃

下面代码至少有 6 个类型安全假象：

```ts
type User = {id: string; profile: {name: string}; roles: string[]}

async function loadUser(id: string): Promise<User> {
  const response = await fetch(`/api/users/${id}`)
  return response.json()
}

async function main() {
  const user = await loadUser('1')
  console.log(user.profile.name.toUpperCase())
  console.log(user.roles[0].toUpperCase())
}
```

任务：

1. 列出编译器被迫相信的所有前提：HTTP status、JSON、字段、数组长度等。
2. 只用标准 TypeScript/JavaScript 写一个从 `unknown` 开始的最小验证器；错误需带 path。
3. 开启 `noUncheckedIndexedAccess`，修复 roles[0]。
4. 禁止在验证器外使用 `as User`/`any`。
5. 写 5 个坏 payload 测试：null、字段缺失、嵌套错误、roles 非数组、数组元素非字符串。
6. 解释类型被擦除后还有哪些安全责任。

## 练习二：结构类型的权限漏洞（高难）

```ts
type PublicUser = {id: string; name: string}
type AdminUser = {id: string; name: string; permissions: string[]}

function cachePublic(user: PublicUser) {
  publicCache.set(user.id, user)
}
```

传入 `AdminUser` 合法，但 cache 若序列化整个对象可能泄漏 permissions。

任务：

- 解释为什么结构类型允许；额外属性检查为什么救不了变量参数。
- 设计 `toPublicUser` 明确投影，保证运行时真的删除敏感字段。
- 比较 `Pick<AdminUser, 'id' | 'name'>`、精确对象工具、Schema strip 和显式构造的安全性。
- 写类型测试与 JSON 输出测试。
- 给代码评审规则：何时“可赋值”不等于“允许跨信任边界”。

