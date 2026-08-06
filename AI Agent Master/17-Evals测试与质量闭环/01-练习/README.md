# 第 17 章练习

## 练习一：客服 Agent Eval Harness

建立 100 条 dataset，覆盖查询、知识、退款提案、拒绝、注入、跨租户、工具失败、长会话。实现 deterministic graders、LLM judge 和人工校准样本。

输出按 slice 的 task/tool/citation/safety/cost/latency，比较两个 prompt 和两个模型。随机 pairwise 顺序，至少重复关键 case 3 次，制定 CI/发布门禁。

## 练习二：从事故到回归

模拟线上 Agent 错误退款、错误引用、循环烧费、泄漏他人数据四起事故。为每起写根因树、最小复现、修复层、regression case、监控报警和回滚条件。禁止只加一句 prompt。
