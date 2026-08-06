# 第 16 章练习

## 练习一：拆分 20 万行 Monorepo

现有单一 tsconfig include `**/*`，web、admin、Node worker、领域代码、OpenAPI 生成物、所有 tests 共用同一 Program；浏览器能看见 Node globals，任何改动全仓 typecheck。

要求：

- 设计 package graph、根 solution 和每包 references。
- 说明哪些包 emit declaration，哪些仅 noEmit。
- 隔离 DOM/Node/test globals，禁止跨包 src 深引入。
- 设计本地增量与 CI clean build/cache 策略。
- 给出基线指标、排查命令和一个月性能预算。
- 解释何时不值得再拆一个 package。

## 练习二：定位一个病态类型（高难）

路由生成器从 1,200 条 route union 计算所有两两跳转许可，再递归生成路径参数和权限组合。`Types` 数、`Instantiations`、内存暴涨，编辑器输入延迟数秒。

要求：

- 设计可重复 benchmark，证明瓶颈而非猜测。
- 保留调用端核心安全：合法 route、对应 params、权限校验。
- 可牺牲非核心“编译期计算所有合法跳转”的精确度。
- 比较 named aliases、non-distributive conditional、对象映射、代码生成、runtime validation 五种手段。

