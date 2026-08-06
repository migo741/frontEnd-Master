# 第 03 章参考答案

事件使用 `Literal` discriminator 和 `TypeAdapter` 做运行时解析；未知类型、额外字段、错误时间全部失败。工具输入和结果分别由 Pydantic 验证，tenant/user/scope 只从可信 `RunContext` 注入，不出现在模型 Schema 中。

## 可运行标准答案

- [Pydantic 协议与泛型 Tool](./reference/solution.py)
- [自动化测试](./reference/test_solution.py)
- [运行说明](./reference/README.md)

