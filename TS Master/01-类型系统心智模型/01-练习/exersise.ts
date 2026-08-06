// 任务：

// 1. 列出编译器被迫相信的所有前提：HTTP status、JSON、字段、数组长度等。
// 2. 只用标准 TypeScript/JavaScript 写一个从 `unknown` 开始的最小验证器；错误需带 path。
// 3. 开启 `noUncheckedIndexedAccess`，修复 roles[0]。
// 4. 禁止在验证器外使用 `as User`/`any`。
// 5. 写 5 个坏 payload 测试：null、字段缺失、嵌套错误、roles 非数组、数组元素非字符串。
// 6. 解释类型被擦除后还有哪些安全责任。

type User = {id: string; profile: {name: string}; roles: string[]}

async function loadUser(id: string): Promise<User> {
  const response = await fetch(`/api/users/${id}`)
  if(!response.ok){
    throw new Error(`Error ${response.status}`)
  }
  const raw = response.json()
  return parseRaw(raw)
}

async function main() {
  const user = await loadUser('1')
  console.log(user.profile.name.toUpperCase())
  console.log(user.roles[0].toUpperCase())
}