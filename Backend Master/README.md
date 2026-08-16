# Backend Master

> 面向已有 JavaScript / Vue 基础、正在补 React 的前端工程师：用 Node.js + TypeScript 完成后端跃迁，最终成为能交付前端、后端、Agent 与生产环境的 AI-native 全栈产品工程师。

本课程不是另一份 CRUD 教程，也不承诺“读完即进大厂”。它的目标是让你拿出高级岗位真正会追问的证据：数据库约束与并发正确性、租户隔离、消息一致性、故障恢复、可观测、容量、部署和安全。

## 为什么这套课适合你

你的 JavaScript 和 Vue 已到中级，React 处于 CRUD 初级。最划算的路线不是清空经验去卷纯 Java/Go 语法，也不是继续叠前端框架，而是：

1. 用熟悉的 TypeScript 把注意力放在后端不变量，而非新语法。
2. 用 PostgreSQL 建立数据、事务与并发的硬基础。
3. 用 Redis、队列、Outbox、SSE 和 OpenTelemetry 学会生产故障语义。
4. 让现有 React Master 成为客户端，AI Agent Master 的 Python worker 成为受限下游。
5. 最终交付一套可部署、可压测、可攻击测试、可恢复的多租户 AI 产品。

## 学完后应能做到

- 从空目录设计并交付一个 Node.js / TypeScript 生产服务，而不把业务规则塞进 Controller。
- 为关系数据设计约束、索引、事务、锁、稳定分页与可回滚迁移。
- 正确实现 Session / OIDC、授权、多租户、审计、幂等 API 和文件边界。
- 把 Redis 当派生设施而非事实来源；按 at-least-once 设计队列消费者。
- 解释并验证 timeout、retry、backoff、circuit breaker、bulkhead、load shedding。
- 让 Node 与 Python Agent worker 通过版本化契约协作，同时守住授权与 HITL 边界。
- 用集成测试、trace、指标、压测、发布和恢复演练证明系统，而不是只画架构图。
- 在系统设计面试中从需求、流量、不变量、数据模型、失败模式和演进路径作答。

## 主线技术栈

| 层 | 课程选择 | 选择理由 |
|---|---|---|
| 运行时 | Node.js 24 LTS、TypeScript 6 strict ESM | 最大化复用你的前端能力；生产以 LTS 为准 |
| HTTP | Fastify 5；补充 NestJS 11 架构映射 | Fastify 薄、便于看清生命周期；NestJS 用于读懂企业项目 |
| 权威数据 | PostgreSQL 18 当前小版本，SQL-first | 约束、事务、MVCC 和查询计划是核心能力 |
| 数据访问 | 原生 SQL / 轻量 query builder；再比较 Drizzle / Prisma | 防止 ORM 把 SQL 和事务问题藏起来 |
| 派生设施 | Redis 8、队列；Kafka 放在需要事件日志时引入 | 按需求选设施，不为简历堆组件 |
| 契约 | OpenAPI / JSON Schema、Problem Details | 让 React、Node、Python 能独立演进 |
| Agent | Python worker | 复用 AI Agent Master；Node 仍掌握身份、授权和业务写入 |
| 交付 | Docker、CI/CD、Kubernetes 基础、OpenTelemetry | 覆盖从开发到运行和恢复的闭环 |

具体 patch 版本会变化。开始学习时先看 [版本策略](./00-学习方法与版本策略.md)，不要把某个小版本背成知识点。

## 课程结构

每章严格按同一顺序：

```text
章节/
├── 00-讲义.md
├── 01-练习/
│   └── README.md
└── 02-答案/
    └── README.md
```

- `00-讲义.md`：先建立不变量、失败模型与生产判断。
- `01-练习/README.md`：只有两题。第一题验证经典正确性，第二题制造生产故障。
- `02-答案/README.md`：提供可复写实现、测试证据、权衡和失败边界。

答案不是“看懂即可”。如果做不出，允许照抄第一遍；随后必须合上答案重写，并改变至少一个约束再验证。

## 六阶段、22 章

### 第一阶段：运行时与服务边界

1. [Node 运行时、进程与资源生命周期](./01-Node运行时进程与资源生命周期/00-讲义.md)
2. [网络、反向代理与 HTTP 语义](./02-网络反向代理与HTTP语义/00-讲义.md)
3. [TypeScript 服务架构、配置与运行时边界](./03-TS服务架构配置与运行时边界/00-讲义.md)

阶段产物：一个可追踪请求、限制资源、处理错误并能优雅关闭的最小服务。

### 第二阶段：PostgreSQL 与数据权威

4. [关系建模、约束与租户数据](./04-PostgreSQL关系建模约束与租户数据/00-讲义.md)
5. [SQL、索引、执行计划与稳定分页](./05-SQL索引执行计划与稳定分页/00-讲义.md)
6. [事务、隔离、锁与并发控制](./06-事务隔离锁与并发控制/00-讲义.md)
7. [Schema 演进、迁移与恢复](./07-Schema演进迁移与恢复/00-讲义.md)

阶段产物：数据库能拒绝重复、越界和并发非法状态，并有迁移、回滚与恢复证据。

### 第三阶段：SaaS 业务边界

8. [身份认证、Session 与 OIDC](./08-身份认证Session与OIDC/00-讲义.md)
9. [授权策略与多租户隔离](./09-授权策略与多租户隔离/00-讲义.md)
10. [API 契约、演进与幂等](./10-API契约演进与幂等/00-讲义.md)
11. [文件、对象存储、Webhook 与第三方边界](./11-文件对象存储Webhook与第三方边界/00-讲义.md)

阶段产物：具备身份、权限、租户、审计、幂等 API、附件和外部集成的 SaaS 核心。

### 第四阶段：异步、分布式与 Agent 边界

12. [Redis 缓存、限流与协同](./12-Redis缓存限流与协同/00-讲义.md)
13. [队列、后台任务与可恢复状态机](./13-队列后台任务与可恢复状态机/00-讲义.md)
14. [Outbox、Inbox、Saga 与跨系统一致性](./14-Outbox-Inbox-Saga与跨系统一致性/00-讲义.md)
15. [超时、重试、熔断、隔舱与过载保护](./15-超时重试熔断隔舱与过载保护/00-讲义.md)
16. [SSE、实时事件、背压与断线恢复](./16-SSE实时事件背压与断线恢复/00-讲义.md)
17. [Node 与 Python Agent 的信任边界](./17-Node与Python-Agent信任边界/00-讲义.md)

阶段产物：关闭 worker、Redis 或模型供应商后，任务仍可恢复，不重复、不错租户、不绕审批。

### 第五阶段：生产质量与交付

18. [后端安全、秘密与 Agent 攻击面](./18-后端安全秘密与Agent攻击面/00-讲义.md)
19. [测试、契约与故障验证](./19-测试契约与故障验证/00-讲义.md)
20. [日志、Metrics、Trace、SLO 与容量工程](./20-日志Metrics-Trace-SLO与容量工程/00-讲义.md)
21. [容器、CI/CD、云发布与灾难恢复](./21-容器CI-CD云发布与灾难恢复/00-讲义.md)

阶段产物：可从空环境部署，可观测、可压测、可灰度、可回滚，并完成恢复演练。

### 第六阶段：统一毕业项目

22. [多租户 AI 工单与运营工作台：毕业项目、系统设计与面试](./22-毕业项目系统设计与面试/00-讲义.md)

毕业项目不是第五个新 Demo。它把现有四套 Master 合并为一套作品：

```text
React Master UI
    → Backend Master：Node/TypeScript 模块化单体
        → PostgreSQL（权威数据）
        → Redis（缓存 / 限流）
        → Queue + Outbox
            → AI Agent Master：Python worker
        → Node 授权 / HITL / 工具执行
    → SSE 向前端投影状态
```

TS Master 提供 Schema SDK；JavaScript 与浏览器课程提供流、网络、安全和性能验证。

## 十条全课不变量

1. PostgreSQL 是事实来源；缓存、队列和 UI 投影均可重建。
2. `tenantId` 只能来自可信身份上下文，不能相信请求体或任意 Header。
3. 网络、队列和模型输出默认会超时、重复、乱序、丢失或撒谎。
4. 副作用必须有幂等键、状态机或可验证的补偿策略。
5. 返回成功前，成功事实必须持久化。
6. Agent 只提出结果或工具意图；Node 服务负责授权、审批和执行。
7. 每个请求、任务与 Agent run 都有 owner、deadline、取消路径和资源上限。
8. 外部输入从 `unknown` 开始；秘密不得进入日志、trace 或模型上下文。
9. 发布兼容前后两个应用版本；备份只有恢复演练成功才有效。
10. 生产能力必须由测试、SQL plan、trace、压测或故障演练证明。

## 先修与跳读

你无需“学完全部旧 Master”才能开课。建议至少掌握：

- Promise、AbortSignal、ESM：见 `《JavaScript 与浏览器高级学习问题》` 第 05、07 章。
- TS 领域建模、运行时 Schema：见 `TS Master` 第 09、10、12 章。
- React 服务端状态和流式 UI：在学到第 16 章前看 `React Master` 第 07、17 章。
- Agent 工具、HITL 与持久执行：在学到第 17 章前看 `AI Agent Master` 第 09、16 章。

如果上述主题已能独立完成练习，直接进入本课；本课不会重复讲通用 Promise、React、RAG 或 Prompt。

## 毕业标准

完成 22 章阅读不是毕业。至少提交以下可复核证据：

- 44 道练习均有第一次实现、测试和复写版本。
- 一份关系模型、约束说明、关键查询 SQL plan 和并发测试。
- 跨租户攻击测试、鉴权矩阵、威胁模型与审计样例。
- 重复消息、worker 崩溃、Redis 故障和模型超时的故障测试。
- 一条 HTTP → DB → Queue → Python worker 的脱敏 trace。
- 容量报告、SLO 与告警、一次灰度回滚和一次备份恢复演练。
- 可访问部署、架构图、ADR、runbook、事故复盘和 10 分钟演示视频。

完整节奏与验收方式见 [学习方法与版本策略](./00-学习方法与版本策略.md)，市场依据见 [市场调研与能力地图](./00-市场调研与能力地图.md)，打卡入口见 [课程总索引](./课程总索引.md)。
