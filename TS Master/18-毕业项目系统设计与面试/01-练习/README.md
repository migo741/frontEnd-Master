# 第 18 章练习

## 练习一：完成毕业项目

按讲义目录实现 `Acme Typed Platform`，必须提交：

- 源码、README、架构图和 5 份 ADR；
- 3 个 endpoints、2 个版本化 events、1 条 NDJSON 流；
- React/Vue 各一个 demo，Node CLI 一个；
- public API/type tests/runtime tests/e2e smoke；
- ESM/CJS 或 ESM-only 的明确决策与 consumer fixtures；
- project references、clean/incremental benchmark；
- TS 5.9/6.0 CI，TS 7 preview 观察报告；
- threat/failure model：坏响应、超大流、race、abort、重复事件、依赖升级。

约束：核心 public API 禁止 `any`；所有 `as` 必须在 review 文档中逐个证明；不得从 adapter 反向依赖框架 core；不得只测源码而不测打包物。

## 练习二：90 分钟高级评审

找同伴或第二天的自己，限时完成：

1. 20 分钟：从需求画信任边界、package graph 和错误模型。
2. 25 分钟：评审一份含 generic fetch、双断言、错误 exports、无取消并发的 PR。
3. 20 分钟：解释 5 个随机面试题，每题给失败案例。
4. 15 分钟：分析一份 extendedDiagnostics，给验证型优化计划。
5. 10 分钟：为 TS 6→7 写 rollout/rollback 决策。

将回答录音或写下来，按答案 rubric 自评。低于 80 分不是失败：把最低的两个维度回炉对应章节，再做一次不同题面的评审。
