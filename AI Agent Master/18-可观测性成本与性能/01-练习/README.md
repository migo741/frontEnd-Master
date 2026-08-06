# 第 18 章练习

## 练习一：Agent Telemetry 规范

为客服 Agent 设计 OpenTelemetry 风格 spans/events/metrics、redaction、sampling 和 retention。实现本地 collector/fake exporter，给 10 条成功/失败 run 生成 trace。

做 dashboard：task success、P95、TTFT、cost/success、tool errors、loops、approval、tenant fairness；为 5 类报警写 runbook。

## 练习二：成本减半实验

在不让关键 slice 质量下降超过门槛的前提下，把 100 条 eval 的 cost/success 降低 50%。尝试 context pruning、tool filtering、model routing、cache、并行、输出限制。逐项单变量实验并报告质量/成本/延迟/variance。
