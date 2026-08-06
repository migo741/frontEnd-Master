# 第 08 章练习

## 练习一：从零实现 Agent Runtime

实现 framework-free runtime，使用 fake model：支持文本 final、一个或多个 tool calls、Pydantic 验证、RunContext 注入、预算、取消、错误 taxonomy、重复动作检测和事件日志。

工具：只读订单查询、价格计算、退款提案（不实际退款）。至少 20 个测试覆盖未知工具、坏参数、越权、并行、部分失败、loop、预算、崩溃恢复。

## 练习二：加入有副作用工具（高难）

新增 `send_email` 和 `create_refund`。设计 proposal → approval → execute；idempotency key、审计、预览、过期批准、批准后参数不可篡改、远端成功本地超时恢复。用故障注入证明不会重复退款/邮件。
