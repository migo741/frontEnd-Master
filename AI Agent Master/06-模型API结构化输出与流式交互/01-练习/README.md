# 第 06 章练习

## 练习一：多供应商模型网关

实现两个 fake provider adapter 和统一 gateway，支持 text、Pydantic structured output、tool calls、stream events、usage、timeout/cancel。能力不支持时 fail fast，不做静默降级。

要求：错误 taxonomy、有限 retry、request id、model registry、价格版本；contract tests 确保两 adapter 行为一致；禁止业务代码 import provider SDK 类型。

## 练习二：断线可恢复的流（高难）

设计 SSE 到浏览器的事件协议。处理上游 tool args 分片、下游断开、event id、重复/乱序、最终 usage、partial content 和 reconnect。说明哪些 provider stream 无法真正从中点恢复，以及如何通过服务端 event log 提供“应用级恢复”。
