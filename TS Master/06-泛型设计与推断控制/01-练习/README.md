# 第 06 章练习

## 练习一：类型安全 DataTable

期望：

```ts
const columns = defineColumns<User>()([
  {key: 'name', header: '姓名', render: value => value.toUpperCase()},
  {key: 'age', header: '年龄', render: value => value.toFixed(0)},
])
```

要求：

- key 只能是 User 的 string key；render value 与具体 key 关联。
- 可选 `sort(a,b)` 参数同字段类型；不可对对象字段默认排序。
- columns 保留 tuple/每项精确类型；调用者不用为每列显式泛型或 `as`。
- rowKey 返回 PropertyKey；rows 接受 readonly User[]。
- 错 key/错误 render/错误 sort 产生局部可读错误。
- 运行时列渲染实现不使用 any；若需局部断言，证明不变量。

## 练习二：步骤状态构建器（高难）

构建 HTTP route：必须依次或在 build 前提供 method、path、handler；auth/schema 可选。`build()` 只能在必需项齐全时出现/可调用。

要求：

- handler 的 params/body/result 从 path/schema 推断。
- `initialState` 等默认值不能反向扩大 schema 类型，使用 `NoInfer` 讨论。
- 比较 phantom generic state builder 与三个纯函数组合的复杂度。
- 生成 `.d.ts` 检查公共类型是否可读、大小可接受。
- 说明什么时候放弃“编译期步骤顺序”，改运行时验证。

限制：最多 3 个显式类型参数暴露给用户；禁止 `as any` 链式逃逸。

