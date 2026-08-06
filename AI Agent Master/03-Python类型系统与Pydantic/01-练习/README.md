# 第 03 章练习

## 练习一：Agent 事件协议

用 Pydantic v2 设计 discriminated union：`TextDelta`、`ToolRequested`、`ToolSucceeded`、`ToolFailed`、`RunCompleted`、`RunFailed`。

要求：严格模式、禁止额外字段；tool args 是 JSON object；error 对外不泄漏 stack/secret；event 有 version/run_id/sequence/time；生成 JSON Schema；静态处理函数穷尽；损坏/未知版本测试不少于 12 个。

## 练习二：类型安全工具定义（高难）

设计泛型 `Tool[ArgsModel, ResultModel]`，能从 Pydantic model 生成输入 Schema、验证模型参数、执行 sync/async handler、验证结果并归一化错误。说明 Python 类型系统无法证明哪些 runtime 事实，以及为何不能让模型选择 tenant_id/user_id/permission scope。
