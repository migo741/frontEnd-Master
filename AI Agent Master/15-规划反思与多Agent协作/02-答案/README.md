# 第 15 章参考答案

答案实现了 bounded planner → 只读 workers → synthesizer → citation verifier。多 Agent 不是“多聊几轮”：每个 worker 都有显式任务、最小权限、搜索预算和结构化结果；冲突证据会保留，失败 worker 不会让系统无限重试。

## 可运行标准答案

- [多 Agent 研究编排器](./reference/solution.py)
- [自动化测试](./reference/test_solution.py)
- [运行说明](./reference/README.md)

