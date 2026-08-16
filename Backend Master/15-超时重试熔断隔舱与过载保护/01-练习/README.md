# 第 15 章练习

## 练习一：有 deadline 和 retry budget 的第三方客户端

实现框架无关 `ResilientClient`：继承父 AbortSignal/绝对 deadline；按错误分类；仅幂等 operation 重试；full jitter；尊重有上限的 Retry-After；滚动 retry budget；closed/open/half-open breaker；所有 timer/listener 清理。

要求用 fake clock/random/transport 写确定性测试：429、503、400、连接超时、调用方取消、deadline 不足、半开只放一个 probe、provider 恢复、写操作 unknown、三层重试放大。

验收：attempt 不越过 deadline；业务 4xx 不计 breaker；open 快速失败；超时写返回 UNKNOWN 而不是自动重做；日志含 operation/attempt/outcome，不含正文/secret。

## 练习二：不会被慢依赖拖死的多租户 API

为“工单摘要”接口实现全局、每 tenant、provider 三层 bulkhead 与有界队列；入口校验 deadline/请求大小/额度，队列满立即 shed。公共读可返回标记 stale 缓存，权限/退款相关调用 fail closed。

压测场景：provider P99 从 200ms 升到 10s、一个 tenant 50 倍流量、Redis 故障导致 cache miss、provider 恢复。给出并发/队列参数依据、SLO、8 个指标、5 条告警和恢复放量策略。

验收：进程内等待数量有硬上限；小 tenant 仍获得份额；DB/provider inflight 不超预算；恢复时无同步重试风暴；降级响应可识别且不伪造新鲜数据。

## 复写任务

关掉答案，从空文件重写 deadline signal、full-jitter retry 和 half-open breaker；再画出网关/SDK/service 各 3 次重试为何可能产生 27 次下游调用。
