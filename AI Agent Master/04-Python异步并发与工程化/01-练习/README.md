# 第 04 章练习

## 练习一：有界并发模型网关

实现 async gateway：按 provider 和 tenant 双重限流；总 deadline；仅对 429/可恢复 5xx 重试；取消传播；记录 usage/latency；响应体上限；client 生命周期复用。

测试：最大并发、Retry-After、jitter（fake clock）、取消时资源关闭、永久错误不重试、写操作 idempotency key、10 万任务不一次创建 10 万 coroutine。

## 练习二：FastAPI 长任务骨架

实现 submit/status/cancel/SSE 四个端点和内存 worker 原型。断开 SSE 时由参数决定取消或继续；服务关闭时停止接单、等待 grace period、持久化未完成 run。说明内存版哪些性质不能用于多实例生产，并设计 PostgreSQL/queue 替代。
