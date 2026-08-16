# 第 19 章练习

两题都要求先列不变量，再决定测试层级。最终报告不能只贴覆盖率百分比。

## 练习一：真实 PostgreSQL 中的 Repository 与并发契约

为 `tool_intents` 或 `agent_runs` repository 建立 Testcontainers 集成测试套件。

约束：

- 测试启动与生产相同主版本的 PostgreSQL；
- 原样执行生产 migrations；
- repository 不得在测试中替换为内存 Map；
- clock 与 UUID 可注入；
- 每个并发参与者使用独立连接；
- 验证唯一约束、FK、租户作用域、事务回滚与 timestamp；
- 用 barrier 让两个执行器同时竞争同一个 intent lease；
- 证明只有一个 claim 成功，失败者得到稳定业务结果而非未处理 SQL 异常；
- 测试数据库重启或连接中断后的错误分类；
- 测试结束后没有连接、timer 或容器泄漏。

提交：容器启动代码、migration runner、repository 测试、并发时间线和 CI 缓存/超时说明。

## 练习二：重复、乱序、重启同时发生的端到端故障测试

为链路编写可重复故障测试：

```text
HTTP create run → PostgreSQL/Outbox → Queue → Python fake worker
→ result event → Node consumer → tool executor → SSE projection
```

测试场景：

1. 同一 HTTP 幂等请求并发两次；
2. Outbox 事件投递两次且结果事件乱序；
3. worker 在 checkpoint 后崩溃并由新 generation 恢复；
4. tool 外部副作用成功后，进程在本地完成记录前崩溃；
5. model adapter 超时，但迟到响应随后出现；
6. Redis 在中途被清空；
7. SSE 断开后从最后连续序号恢复。

最终断言：

- PostgreSQL 只有一个 run；
- tool 外部副作用最多一次，或能通过供应商 idempotency key 对账为一次；
- 状态最终为唯一合法终态；
- 不存在跨租户记录；
- 事件序号连续，终态后无迟到写入；
- Redis 可由数据库恢复；
- 每个失败能用同一 trace/run ID 关联。

禁止使用真实付费模型；fake provider 必须支持可控分块、超时、迟到与错误注入。
