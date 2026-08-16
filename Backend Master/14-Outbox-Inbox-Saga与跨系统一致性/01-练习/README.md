# 第 14 章练习

## 练习一：不丢也不重复入账的订单事件

订单服务批准订单时更新 aggregate version 并写 `OrderApproved.v1` outbox。两个 relay 并发发布；消费者创建账单并用 inbox 去重。实现 PostgreSQL schema、生产事务、relay claim/mark、consumer 事务和测试。

故障点：业务提交前后 crash、publish 前后 crash、ack 丢失、同 event 并发、同 id 不同 payload、aggregate v3 先于 v2、consumer commit 后 ack 前 crash、outbox 积压清理。

验收：批准成功最终必有事件；重复事件只产生一笔账单；payload 冲突报警；版本缺口不乱应用；outbox/inbox 可安全重放并有 retention 说明。

## 练习二：可补偿的库存—支付—工单 Saga

设计 `reserve inventory -> authorize payment -> create ticket -> capture payment`。使用显式 orchestrator、每 step 稳定 operation id、乐观 saga version、outbox command/inbox result；定义取消与逆序补偿。

要求处理：库存成功后支付拒绝、支付超时但实际成功、创建工单重复、capture 后取消、补偿失败、迟到 success 到达已 compensating saga、部署期间 step schema 升级。

验收：不可逆 capture 尽量最后；未知支付先查单；任何迟到事件不能非法倒退状态；补偿是可观察的新业务操作；超过收敛 SLO 进入人工队列。

## 复写任务

关掉答案，重写“业务 + outbox”与“inbox + 业务”两个本地事务；画出 publish 成功但 mark 失败为何只造成安全重复，再说明 Saga 补偿为什么不是数据库 rollback。
