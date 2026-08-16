# 第 10 章练习

## 练习一：并发安全的退款 API

实现 `POST /v1/tickets/:id/refunds`。请求必须带 `Idempotency-Key` 和 ticket version；相同 tenant、actor、operation、key、请求体重试返回完全相同的 status/body；同 key 换金额返回 409。

要求：

1. PostgreSQL 持久化 key、fingerprint、processing/completed/failed 与响应。
2. 两个并发首次请求最多创建一笔 refund；进程在提交前后 crash 都有明确恢复语义。
3. ticket version 过期返回稳定错误；key 与 version 的职责不能混淆。
4. 至少 10 个测试：并发、重放、key 误用、超时、业务拒绝、DB 失败、跨 tenant、跨 actor、TTL、日志脱敏。

验收：不能用进程内 Map 作为事实源；金额使用整数最小单位；HTTP adapter 之外的 service 可直接测试。

## 练习二：不打断旧客户端的 v1 演进

已有 v1 工单 API 返回 `status: 'open'|'closed'`，现在需要 `waiting_customer`、结构化 assignee 和游标分页。设计兼容发布，提交 OpenAPI diff 策略、v1/v2 adapter、旧 consumer fixture 和弃用仪表盘。

要求处理：旧客户端遇到新枚举、字段由 string 变 object、offset 到 cursor、错误格式迁移、服务端灰度回滚。至少提供一份可运行 contract test，证明旧 fixture 在新 provider 上仍通过。

验收：内部数据库模型不直接成为 DTO；不能以“前端一起发版”作为唯一兼容策略；说明何时必须开 v2，何时只做可选扩展。

## 复写任务

从空文件重写 key claim/fingerprint/响应重放，并画出“请求超时但事务已提交”时间线；再用 150 字解释为什么幂等键、唯一约束和 If-Match 不能互相替代。
