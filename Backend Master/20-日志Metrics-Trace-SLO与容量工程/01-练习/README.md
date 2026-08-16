# 第 20 章练习

不接受只安装一个监控 SDK 或贴一张 CPU 图。两题都要从用户结果出发。

## 练习一：贯通 HTTP → DB → Queue → Python 的安全 Trace

为“创建并执行 Agent run”建立 OpenTelemetry 链路。

约束：

- Node HTTP、PostgreSQL、Outbox、queue publish/consume、Python worker、model call、tool intent 都有合理 span；
- 队列消息注入/提取 W3C `traceparent`；
- 不信任客户端 baggage，不从 trace 得出 tenant 身份；
- span 名称低基数，真实 run ID 只作为受控 attribute；
- Prompt、Cookie、Authorization、数据库语句参数和 tool secret 不进入遥测；
- 日志自动附加 trace ID，并验证 redaction；
- model error、deadline、取消和重试使用稳定 error attributes；
- token 流不为每个 token 建 span；
- exporter 故障不能阻塞业务主路径；
- 至少一条 trace 能区分 queue wait、model latency 与 SSE delivery。

提交：Node/Python 初始化、消息传播代码、脱敏测试、trace 截图或 JSON，以及一次失败诊断叙述。

## 练习二：Agent SLO、Burn-rate 告警与容量拐点

定义并测量至少四个 SLI：

1. run 正确完成率；
2. 首次有意义事件延迟；
3. 端到端完成时间；
4. 单位成功成本；
5. 可选：queue wait 或获批工具正确执行率。

约束：

- 每个 SLI 明确事件来源、分子、分母、排除项和数据延迟；
- 为最重要旅程设置 28 天 SLO；
- 给出多窗口 burn-rate 告警与 runbook；
- metric 不使用 `tenantId/runId/userId` label；
- 用 k6 或同类工具模拟普通流量、突发、热租户、慢模型与 5% 依赖错误；
- 逐步升压直到吞吐不再线性增加；
- 记录 p50/p95/p99、错误率、queue age、DB pool、event-loop lag、worker 饱和和成本；
- 找出第一个容量拐点，做一次修改后以同样负载回归；
- 给出当前 safe operating limit，而不是理论最大值。

证据必须包含负载脚本、原始结果、dashboard、计算过程和优化前后对比。
