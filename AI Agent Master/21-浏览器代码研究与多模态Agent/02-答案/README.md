# 第 21 章参考答案

答案实现一个来源受限的研究 Agent 和代码补丁策略层：页面内容永远按不可信数据处理，只有显式 `FACT:` 证据进入 claim-evidence graph；引用必须逐 claim 验证。代码 Agent 只能改 workspace 内允许的文件，限制 diff/命令，并且没有 push 与 secret 权限。

## 可运行标准答案

- [研究与代码 Agent 安全内核](./reference/solution.py)
- [自动化测试](./reference/test_solution.py)
- [运行说明](./reference/README.md)

