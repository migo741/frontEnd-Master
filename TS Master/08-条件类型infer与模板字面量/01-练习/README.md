# 第 08 章练习

## 练习一：路由参数解析

支持语法：

```text
/users/:id
/org/:orgId/reports/:reportId
/files/*path
/search/:query?
```

目标：

```ts
route('/org/:orgId/reports/:reportId', params => {
  params.orgId      // string
  params.reportId   // string
})
```

要求：

- 模板字面量推导必选、可选和 catch-all（catch-all 是 string[]）。
- runtime matcher/decoder 与静态语法一致，URL decode 错误可处理。
- 重名 param、空名、多个 catch-all 在 runtime 拒绝；类型尽量给错误，但不牺牲可维护性。
- 非字面量 `string` path 降级为 `Record<string,string|string[]|undefined>`，不能假装精确。
- 类型测试覆盖 union path，并说明希望分布与否。

## 练习二：有限深 `DeepReadonly`（高难）

设计仅用于 JSON-like domain 的 `DeepReadonly<T, Depth=5>`：

- primitive 原样；tuple 保留 tuple；array 变 readonly；object 属性 readonly；union 分布。
- Depth 到 0 后停止递归并返回 T（或 unknown，选择并解释）。
- Date/Map/Set/Function 不在输入域；若传入给清晰错误/按叶处理。
- any/never/unknown 行为有测试。
- 生成 1,000 字段/8 层 fixture，测 typecheck/IDE；与内建 Readonly 对比。

最后写决策：为什么公共业务 API 可能只接受 `Readonly<T>` 而非 DeepReadonly。

