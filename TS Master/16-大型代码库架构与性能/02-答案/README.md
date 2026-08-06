# 第 16 章参考答案

## 练习一

建议最少拆 `domain`、`application`、`api-generated`、`sdk`、`react-adapter`、`web/admin`、`worker`。domain/application/generated/sdk 发声明并 composite；最终 Vite apps 可 noEmit，由 bundler 输出；worker 按 Node 配置输出。tests 作为独立配置或紧邻包的检查 target，不把 globals 注入生产 Program。

根 `tsc -b` 只 references 顶层 target；每包只能经 package exports 依赖，lint 禁止 `packages/x/src/*`。task graph 缓存包含 lockfile、TS/生成器版本、config 与源码；CI 定期 clean build，避免缓存长期隐藏问题。

基线记录冷/热 build、单包修改、内存、Files/Types/Instantiations、编辑器首诊断。一个月目标可定为关键 runner 冷构建 P95 不回退 15%，单包增量 P95 小于团队阈值，并对声明体积增长报警。是否拆包取决于独立所有权/部署/依赖边界和是否能缩小重建范围；只有目录美观价值时不拆。

## 练习二

创建最小固定 route fixture，锁定 Node/TS 版本，用 `--extendedDiagnostics` 多次比较中位数，再用 `--generateTrace` 确认实例化热点。分别保留 100/300/600/1200 route 看增长曲线；若近二次/指数，才能归因组合计算。

重构为生成一个 `RouteMap`：key 是 route name，value 是 params/permission。导航 API 泛型只按一个 key 做 indexed access，不在调用时分配整个 union；跳转许可由构建时生成 adjacency Map 或 runtime 查询。模板字面量 path params 可在生成阶段产出每条命名类型，避免反复递归解析。

named alias 能缓存/改善诊断但不一定消除组合；`[T] extends [U]` 可阻止无意分配；对象映射把两两 union 变按 key 查询；代码生成把稳定计算移出 checker；runtime Schema 负责外部 route 数据。核心安全仍保留为 `navigate<K extends keyof RouteMap>(key: K, params: RouteMap[K]['params'])`。用同一 benchmark 验证实例化和延迟下降，而不是只看代码变短。
