# 第 21 章练习

部署平台可选 Kubernetes、ECS 或受管容器平台，但必须证明相同不变量。下面以容器和 Kubernetes 表述。

## 练习一：不可变制品、兼容迁移与 Canary 发布

为 Node API 和 Python worker 建立发布流水线。

约束：

- 多阶段构建、锁文件安装、固定基础镜像、非 root；
- 运行镜像不含源码秘密、编译缓存和开发依赖；
- 生成 SBOM、扫描严重漏洞、签名镜像；
- CI 使用 OIDC/工作负载身份，不保存长期云 key；
- unit、Node/Python 契约、Testcontainers 集成、E2E 均为门禁；
- migration 独立运行，使用 expand/contract，支持 N/N-1 共存；
- startup/readiness/liveness 各自语义正确；
- SIGTERM 时先 unready，再排空 HTTP/SSE/queue，截止时间内退出；
- 以镜像 digest canary 5% → 25% → 100%；
- 自动分析错误率、run 正确率、queue age、成本和安全拒绝；
- 自动回滚使用旧 digest，且数据库与消息保持兼容。

提交 Dockerfile、部署清单、CI pipeline、migration 计划、回滚演练与制品 provenance。

## 练习二：满足 RTO/RPO 的跨组件灾难恢复演练

为毕业项目定义业务认可的 RTO/RPO，然后在隔离环境演练：

```text
PostgreSQL 主库不可恢复
对象存储仍可访问但部分对象版本混乱
Redis 全丢
队列中存在未确认与重复消息
外部工具可能已成功但本地结果晚于恢复点
```

约束：

- 使用全量备份 + WAL/PITR 恢复 PostgreSQL 到指定时间；
- 校验备份解密、schema 版本、行数与业务不变量；
- 用 manifest 校验对象引用、hash 与孤儿对象；
- Redis 从权威数据或流量重建；
- 从 Outbox 重发恢复点后的 durable intent；
- Inbox/幂等键阻止重复工具副作用；
- 对结果未知的外部操作执行 reconciliation，不盲目重放；
- 防止旧区域恢复后双写；
- 记录实际 RTO、实际数据损失和人工步骤；
- 演练后把至少一个手工步骤自动化。

提交 runbook、时间线、校验 SQL、恢复后 smoke/E2E、证据清单和复盘。
