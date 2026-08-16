# 第 05 章练习

## 练习 1（经典必做）：用 plan 证明工单列表索引

准备至少 50 万条 ticket，包含一个超大租户、多个小租户和倾斜 status。优化两条查询：

1. 指定 tenant + 单一 status，按 `created_at DESC, id DESC` 取 51 条。
2. 只指定 tenant，采用相同排序取 51 条。

交付：建索引前后 `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`、索引 DDL、写入代价说明和为何不使用 `SELECT *`。必须证明结果顺序稳定，不能只截图“出现 Index Scan”。

验收关注 actual/estimated rows、Rows Removed、Sort、heap fetch、buffer hit/read 与总时间；不得通过关闭 seqscan 作弊。

## 练习 2（高难）：带签名的稳定 keyset cursor

实现 `listTickets({ tenantId, status, limit, after })`：

- tenantId 只来自可信调用上下文。
- 两种 SQL 分别服务“有 status”和“无 status”，避免可选 OR 破坏计划。
- cursor 包含 `v/status/createdAt/id`，HMAC-SHA256 签名，最大 1024 字节。
- 严格验证字段、规范 UTC 时间、UUID、签名和过滤条件；错误统一为公开 `INVALID_CURSOR`。
- 获取 `limit + 1`，最多返回 100 条，next cursor 指向最后返回行。

集成测试插入大量相同 `created_at` 的行，并在第一页后插入一条更新记录；遍历结果不得重复。改变 status、篡改 token、错签名和超长 token 必须失败。

说明删除、状态变化和排序键更新时本协议承诺什么、不承诺什么。
