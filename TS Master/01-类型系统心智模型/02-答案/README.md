# 第 01 章参考答案

## 练习一

`response.json()` 在 DOM 类型中产生宽松数据（历史上常为 any），`Promise<User>` 返回注解只是承诺。还未检查 response.ok/content-type、JSON 可解析、值为对象、profile/name/roles 存在且类型正确、roles 非空。

最小解析器：

```ts
type User = {id: string; profile: {name: string}; roles: string[]}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function parseUser(value: unknown, path = '$'): User {
  if (!isRecord(value)) throw new Error(`${path}: expected object`)
  if (typeof value.id !== 'string') throw new Error(`${path}.id: expected string`)
  if (!isRecord(value.profile)) throw new Error(`${path}.profile: expected object`)
  if (typeof value.profile.name !== 'string') {
    throw new Error(`${path}.profile.name: expected string`)
  }
  if (!Array.isArray(value.roles)) throw new Error(`${path}.roles: expected array`)
  for (const [index, role] of value.roles.entries()) {
    if (typeof role !== 'string') throw new Error(`${path}.roles[${index}]: expected string`)
  }
  return {id: value.id, profile: {name: value.profile.name}, roles: [...value.roles]}
}

async function loadUser(id: string): Promise<User> {
  const response = await fetch(`/api/users/${encodeURIComponent(id)}`)
  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  const raw: unknown = await response.json()
  return parseUser(raw)
}
```

索引：

```ts
const firstRole = user.roles[0]
if (firstRole !== undefined) console.log(firstRole.toUpperCase())
```

类型擦除后仍需鉴权、输入大小、原型污染/特殊对象、业务约束、错误脱敏和网络失败。生产更适合成熟 Schema 库，第 10 章会做单一源设计。

## 练习二

`AdminUser` 包含 PublicUser 所需全部属性，所以结构上可赋值。额外属性检查只针对新鲜字面量的常见错误，并不把对象裁剪；类型工具也不改变运行时对象。

```ts
function toPublicUser(user: AdminUser): PublicUser {
  return {id: user.id, name: user.name}
}

function cachePublic(user: AdminUser) {
  publicCache.set(user.id, toPublicUser(user))
}
```

`Pick` 只计算静态视图：

```ts
const publicView: Pick<AdminUser, 'id' | 'name'> = admin
JSON.stringify(publicView) // 运行时仍可能包含 permissions
```

显式构造或配置为 strip unknown keys 的运行时 Schema 才真正投影。跨日志、缓存、网络、客户端序列化等信任边界时，必须建立显式 DTO/serializer 并测试实际 bytes；“能赋值给 DTO 类型”不代表敏感字段已删除。

