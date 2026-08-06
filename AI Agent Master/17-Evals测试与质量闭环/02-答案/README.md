# 第 17 章参考答案

答案不是用“看起来不错”评 Agent，而是把数据集、候选输出、deterministic grader、slice 指标、pairwise 顺序和发布门禁写成代码。`build_dataset()` 生成 100 条覆盖正常、拒绝、跨租户、注入和工具失败的基线数据。

## 可运行标准答案

- [Eval harness](./reference/solution.py)
- [100 条数据集生成器](./reference/generate_dataset.py)
- [自动化测试](./reference/test_solution.py)
- [运行说明](./reference/README.md)

