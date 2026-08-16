# 第 09 章练习

## 练习一：三层防线的工单授权

实现多租户工单的 read/update/refund：应用策略使用 RBAC + owner/assignee 关系 + 状态/金额条件；repository 所有 API 显式接收 tenant；PostgreSQL 开启 RLS 和 tenant 复合外键。

要求：

1. 普通 agent 只能读所属租户且分配给自己的工单；manager 可更新本租户；refund 还要求批准状态和金额限额。
2. tenant 从 authenticated principal 获得，请求体中的 tenant 字段被拒绝或忽略。
3. 写入在同一事务中重新检查状态/version；审计 allow/deny 与 policy version。
4. 写矩阵测试和属性测试，覆盖列表、详情、猜 id、批量更新、连接池复用与 owner 账号。

验收：删除任一应用层 tenant filter 后，RLS 测试仍阻止泄漏；关闭 RLS 的测试环境必须显式失败，不能静默继续。

## 练习二：不会越权的异步导出

设计“导出本租户近 30 天工单”任务。创建 API、队列 payload、worker、对象存储 key、下载 URL 和审计都要保持 tenant/actor 边界。

故障与攻击：提交伪造 tenant、创建后被移出租户、worker 重试、缓存复用、对象 key 猜测、管理员跨租户支持、导出完成后权限撤销。

验收：明确采用“执行时当前权限”还是“批准快照”，并说明产品语义；普通 worker 不具备无审计跨租户查询权；下载 URL 短期且绑定授权；20 个 tenant 并发任务不串日志/文件。

## 复写任务

关掉答案，独立重写 RLS policy、transaction-local tenant context 与纯 policy 函数；再写一个故意漏 tenant 的 repository 测试，证明数据库会拒绝。
