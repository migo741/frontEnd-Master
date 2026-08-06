# 第 16 章参考答案

答案用 SQLite 做可运行的 durable runtime 原型：run/event checkpoint、带 fencing token 的 worker lease、审批内容哈希与过期时间、幂等 operation。SQLite 便于本地学习；生产可映射到 PostgreSQL，并补 outbox、队列和 schema migration。

## 可运行标准答案

- [持久运行时](./reference/solution.py)
- [自动化故障测试](./reference/test_solution.py)
- [运行说明](./reference/README.md)

