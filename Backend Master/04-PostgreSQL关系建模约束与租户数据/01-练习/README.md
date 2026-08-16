# 第 04 章练习

## 练习 1（经典必做）：让数据库拒绝错租户工单

为 `tenant`、`account`、`ticket` 设计 PostgreSQL 18 DDL。必须满足：

1. 同租户规范化邮箱唯一，跨租户可重复。
2. 工单 requester 与 creator 必须属于工单 tenant。
3. 状态只有 `open/in_progress/resolved/closed`，优先级只有 `low/normal/high/urgent`。
4. `updated_at >= created_at`；核心列全部明确 NULL 语义。
5. 删除账户时若仍被工单引用必须失败；租户不得用一次无审计 CASCADE 物理删除。
6. 所有约束有稳定名称，外键 referencing columns 有合适索引。

写至少 8 条数据库集成断言，其中必须含重复邮箱、跨租户引用、非法状态和时间倒流。说明哪些规则刻意没有放进 ORM。

## 练习 2（生产攻击）：RLS 默认拒绝

创建非 owner 的 `app_runtime` 角色与 tenant RLS policy，并写 Node 集成测试证明：

- tenant A 查询看不到 tenant B。
- 在 tenant A context 下，即使 INSERT 显式写 tenant B 也失败。
- 没有 tenant context 时 SELECT 返回 0 行，INSERT 失败。
- 事务结束并归还连接后，tenant context 不残留。
- app role 无法关闭 RLS、不能 SET ROLE 为 owner。

约束：用参数化 `set_config('app.tenant_id', $1, true)` 设置事务局部 context；不得信任 body/header 中的 tenant ID。记录预期 SQLSTATE，不只匹配错误文本。

复写时加入后台管理员路径：只能使用独立凭证和显式审计，不能给普通 app pool `BYPASSRLS`。
