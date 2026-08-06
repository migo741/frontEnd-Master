# 第 13 章练习

## 练习一：从 CRUD 仓库到可扩展架构

现状：Vite SPA，所有文件在 `src/components`，axios 单例直接导入，token 在 localStorage，Redux 存接口数据，20 人将开发订单/库存/客服三个域。

任务：

- 输出目标目录/包图和允许依赖方向；用自动规则阻止越界。
- 设计 composition root、API adapter、Router/Query/feature store 边界。
- 给“订单详情”做一次纵切迁移，不大爆炸重写。
- 定义共享 UI、业务 pattern、领域组件的归属规则。
- 解决 token/认证迁移，不允许只改变量名。
- 写 ADR：单仓模块化 vs monorepo vs 微前端，结合 20 人规模选择。
- 给迁移提供 feature flag、观测、回滚和删除旧代码计划。

交付物：`ARCHITECTURE.md`、一张依赖图、一个可运行纵切、两个边界测试。

## 练习二：组件库发布门禁（高难）

设计 `@company/ui` 的 Button/Dialog/FormField/DataTable 交付流程。

要求：

- package exports、类型、ESM、CSS side effects、React peer dependency 兼容策略。
- Story/交互/RTL/视觉/a11y/消费者构建测试分层。
- semver、changeset、预发布、codemod/弃用周期。
- bundle 预算与 tree-shaking 验证；不能 import Button 就打入 DataTable。
- React 18/19 ref 类型差异和 RSC `use client` 边界策略。
- 漏洞紧急修复流程：发现严重 Dialog 逃逸/依赖漏洞后，如何定位消费者、发补丁、灰度、强制升级。

写一个 `Button` API 的“差 API → 兼容迁移 → 删除旧 prop”示例。

