# 第 04 章参考答案

实现不预创建海量 coroutine 的固定 worker pool；总 deadline 贯穿每次 attempt，永久错误不重试。长任务 API 使用幂等提交、取消意图和事件流，生产时再替换为 PostgreSQL 与消息队列。

## 可运行标准答案

- [异步并发与 Run Service](./reference/solution.py)
- [自动化测试](./reference/test_solution.py)
- [运行说明](./reference/README.md)

