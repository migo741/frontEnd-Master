# 第 16 章练习

## 练习一：跨天采购 Agent

流程：收集需求 → 搜供应商 → 比价 → 合规 → 人工批准 → 下单 → 等外部确认 → 通知。批准可能等待 48 小时，期间可部署升级。

设计 PostgreSQL event/state、worker lease、checkpoint migration、approval、operation id、outbox、cancel/compensation。对 12 个 crash/竞态点做故障注入。

## 练习二：Durable Runtime 选型

用同一最小 workflow 分别做 LangGraph persistence 和一种通用 durable runtime 的原型。比较重放、HITL、timer/signal、活动幂等、版本升级、trace、团队运维和成本；写 ADR，不以“框架更火”作结论。
