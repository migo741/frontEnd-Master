# 第 08 章参考答案

运行时以显式状态和事件驱动；模型只提出 ToolCall，应用执行白名单、scope 和控制字段检查。未知工具与业务错误作为结构化结果回给模型。写操作使用 proposal hash、批准和稳定 operation id。

## 可运行标准答案

- [手写 Agent Runtime](./reference/solution.py)
- [自动化测试](./reference/test_solution.py)
- [运行说明](./reference/README.md)

