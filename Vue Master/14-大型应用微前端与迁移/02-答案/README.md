# 答案与复盘

## 题 1

当前证据首先支持“模块化单体 + 可选 Monorepo 包”，不支持运行时微前端。主要痛点是非法依赖和构建/发布流程，不是独立部署刚需。决策：引入 feature public API、依赖 lint、ownership；将 design system/contract/build config 拆 workspace 包，应用仍单部署；增量缓存和受影响任务降低 CI 时间。

反证：若某团队必须每日独立发布且中央发布成为业务瓶颈；某 feature 需强故障隔离；跨技术栈收购团队无法同步升级，则重新评估微前端。3 个月指标：非法依赖归零趋势、p95 CI < 6 分钟、发布冲突 < 每月 1 次、变更失败率不升。达不到先分析治理执行，不自动跳微前端。

## 题 2

阶段 0 建基线：关键 E2E、错误率、性能与 bundle；冻结新增 Vue 2 特有模式。阶段 1 升级构建/TypeScript/lint，在兼容构建中运行，建立 router/store/API adapter。阶段 2 按低耦合路由迁 Vue 3，行为对比与按路由开关回滚；新模块只写 Vue 3。阶段 3 迁核心共享基础设施和剩余模块，移除 compat warning。阶段 4 才清理 Vuex/旧构建和无用 adapter。

优先测试登录、权限、支付/提交、深链和大表格；不迁移稳定、即将下线或无业务 owner 的页面。每阶段记录错误率、性能、交付 lead time 和 compat warnings。大规模机械改写应由 codemod 完成，人力用于语义差异和边界。

