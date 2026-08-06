# 第 15 章练习

## 练习一：研究报告系统 A/B

分别实现：单 Agent；planner + search workers + synthesizer + citation verifier。任务需多来源检索、矛盾证据和引用。

用 25 条数据比较成功、引用正确、覆盖、成本、P95、variance；至少制造 worker 失败、证据冲突、重复搜索和 supervisor loop。依据结果决定是否保留多 Agent。

## 练习二：跨权限协作

设计客服 Agent（只读）、财务 Agent（退款提案）、合规 Agent（规则检查）、唯一执行器。定义 handoff/task/result Schema、权限、预算和审批。证明任何 Agent 被 prompt injection 控制后仍不能直接退款或读取其他 tenant。
