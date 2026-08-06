# 第 02 章练习

## 练习一：类型安全配置注册表

构建路由配置：

```ts
type Feature = 'home' | 'billing' | 'admin'
```

要求：

- 配置必须恰好覆盖所有 Feature；每个 path 是 `/${string}`。
- `admin` 的具体 path 能推断为 `'/admin'`，不能被拓宽成 string。
- `roles` 若存在必须为非空 readonly 数组；home 禁止 roles。
- `getPath('billing')` 返回对应字面量；错误 feature 编译失败。
- 禁止 `as RouteConfig` 和 non-null assertion。
- 运行时 `Object.keys` 的 string[] 边界要局部安全处理。

比较三版：显式注解、`as const`、`as const satisfies`；解释调用端差异。

## 练习二：给 20 万行旧项目开启严格模式（高难）

旧项目当前：`strict:false`，全局 DOM+Node+Jest 类型混在一起，3,000 个隐式 any，1,500 个索引读取，广泛使用 `{x?: T}` 表示“缺失/清除/不修改”三种语义。

任务：

- 给分阶段开关顺序、错误基线和 CI 策略；业务开发不能冻结三个月。
- 浏览器/Node/测试拆 tsconfig，解释 TS 6 `types: []` 影响。
- 为 optional patch 设计迁移模型，不能机械加 `| undefined`。
- 设置 `@ts-expect-error`/any budget 和到期治理。
- 设计 codemod 能做与不能做的边界。
- 给成功指标：错误下降之外至少包含缺陷、构建时间、编辑器延迟、PR 返工。

交付一份迁移 ADR 和 4 周试点计划。

