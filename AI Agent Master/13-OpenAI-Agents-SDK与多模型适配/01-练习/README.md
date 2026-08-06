# 第 13 章练习

## 练习一：迁移为 Agents SDK

把第 08 章客服 runtime 的“查询+提案”部分迁到 OpenAI Agents SDK Python：function tools、Pydantic output、context、guardrail、handoff 和 tracing。退款执行仍走自有 ToolExecutor/审批。

使用 fake/model stub 完成确定性测试；用少量真 API eval 比较迁移前后任务、轨迹、token、延迟。写 ADR 说明哪些状态不交给 SDK session。

## 练习二：模型路由与故障转移

设计 provider-neutral request + capability registry。三档模型承担抽取、普通 Agent、困难规划；故障转移不能破坏 structured/tool 语义。加入数据地域、成本、延迟、tenant policy。用 eval 证明路由优于全量大模型。
