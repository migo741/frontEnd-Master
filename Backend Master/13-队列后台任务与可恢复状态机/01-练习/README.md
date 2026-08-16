# 第 13 章练习

## 练习一：能从 worker crash 恢复的报表任务

实现 PostgreSQL 18 job table 与 worker：提交、claim、heartbeat、checkpoint、complete、fail/retry、cancel。任务分“读取分页 → 写对象分片 → 合并 artifact”三步；每步可重复，artifact key 含 job/step/version。

要求：`FOR UPDATE SKIP LOCKED` 批量 claim；lease + 单调 fencing；指数退避；最大 5 次；Schema 错直接 failed；running cancel 在安全点生效；两个 worker 不能都完成同一 fencing generation。

故障测试：claim 后 crash、外部写后 DB 前 crash、heartbeat 暂停、旧 worker 恢复、ack 丢失、对象已存在、取消与完成竞态、部署新 schema。验收以数据库/artifact 最终不变量为准。

## 练习二：多租户公平调度与 DLQ 运维

设计 100 tenant 的邮件/导出队列。一个恶意 tenant 瞬间提交 10 万 job，不能让其他 tenant 饿死；邮件 provider 429 时不得形成重试风暴。

实现 admission limit、每 tenant/type concurrency、weighted round-robin 或等价公平 claim、Retry-After、DLQ 与带审计的 replay。提供状态 API 和 8 个指标/5 条告警。

验收：大 tenant 满载时小 tenant 的 oldest age 仍在 SLO；队列有硬上限；DLQ replay 沿用 operation id；Redis/queue 短故障不会丢 PostgreSQL job。

## 复写任务

关掉答案，重写 claim + fencing finish 两条 SQL；画出“外部对象已写、DB complete 前 crash”的恢复流程，并解释为什么消息 ack 不能替代业务幂等。
