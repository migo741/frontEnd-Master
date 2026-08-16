# 第 06 章：数据访问、BFF 与契约治理

> 版本基线：截至 2026-08-16。协议工具会演进；身份、领域所有权、兼容、故障和观测责任必须长期明确。

## 1. 市场与业务问题

复杂前端很少只调用一个稳定接口。
一个页面可能组合用户、权限、订单、推荐、实验和第三方数据，还要支持 Web、移动端和 AI 流式交互。
如果浏览器直接理解所有领域服务，客户端会承受网络瀑布、版本传播、身份和故障组合成本。
如果 BFF 吞下所有逻辑，又会形成没有领域所有权的第二后端。
架构目标是让每层只承担它有上下文、有权限、也有能力长期运营的责任。

## 2. 本章非目标

- 不教 REST、GraphQL、RPC、Fetch 或 Node 框架 API。
- 不重讲数据库事务和后端缓存实现。
- 不认为每个前端都需要独立 BFF。
- 不用自动生成 TypeScript 类型替代运行时验证和兼容治理。

## 3. 三层责任模型

**浏览器/客户端**负责呈现、交互、用户意图、局部状态和可取消请求。
**BFF**负责客户端特有的身份会话、聚合、裁剪、协议适配和体验级降级。
**领域服务**负责业务不变量、授权事实、事务、持久状态和跨客户端一致语义。
API Gateway 通常处理入口路由、TLS、基础认证、配额和流量策略，不等同于 BFF。
边界以责任判断，不以进程或团队名称判断。
BFF 可以与前端同仓，也可以独立部署；关键是所有权和失败域是否清楚。

## 4. BFF 何时值得

- 多个后端请求造成可测量的客户端瀑布和失败组合。
- 不同客户端需要明显不同的数据形状或发布节奏。
- 浏览器不应直接持有上游凭证或接触内部拓扑。
- 需要把多种协议适配为流、分页或客户端友好错误。
- 服务端渲染需要同一身份和数据装配边界。
- 团队能承担 BFF 的容量、安全、值班和版本责任。

只有一个稳定 CRUD 服务、一个客户端和简单会话时，直接 API 往往更经济。

## 5. BFF 不应拥有的内容

BFF 不复制退款规则、库存不变量、租户授权事实或核心状态机。
它不能通过并行调用模拟跨服务事务。
不能因为“离前端近”就跳过服务端授权。
不能长期维护一份与领域服务不同的客户、订单或权限模型。
业务规则若只对某个体验成立，也应命名和测试其所有权，而不是藏在 resolver。
当多个客户端都需要同一逻辑时，应评估把它下沉到领域服务或共享服务。

## 6. 身份、Session 与租户边界

浏览器使用安全 Session/Cookie 或明确的短期 token，不接触服务间 secret。
BFF 从可信认证上下文取得 principal 和 tenant，不能相信请求体的 tenant id。
向下游传播最小身份声明、请求 id、deadline 和授权上下文。
领域服务仍按资源和动作重新授权，不把“来自 BFF”当作 allow。
跨租户支持、代操作和 break-glass 必须显式建模并审计。
服务端渲染缓存和 BFF 聚合缓存都不能漏掉身份维度。

## 7. 契约不是一份文档

契约包含输入、输出、错误、状态码、顺序、分页、幂等、时限和兼容承诺。
OpenAPI、GraphQL Schema 或 IDL 只是机器可读载体。
生产者 fixture、消费者契约、Schema diff 和运行时遥测共同形成治理闭环。
数据库实体、内部事件和外部 DTO 不应是同一个类型。
契约 owner 要回答谁能扩展、谁能弃用、支持多久和如何通知消费者。
文档中“可选”字段若所有客户端都假设存在，仍是事实上的必填契约。

## 8. 类型生成与运行时边界

代码生成可以减少拼写和静态类型漂移。
网络响应在运行时仍是 `unknown`，尤其来自第三方、缓存、灰度和旧服务。
在信任边界做 Schema 验证，并把失败转为有界错误和遥测。
不要在每个组件重复解析；由数据 adapter 输出稳定领域视图。
生成客户端需要可审查的重试、超时、日志和错误策略，不能隐藏副作用。

生成物版本应与 Schema 和生成器版本可追溯。

## 9. REST、GraphQL 与 RPC 的权衡

REST 容易利用 HTTP 语义、缓存和独立资源演进，但聚合可能产生多请求。

GraphQL 让客户端声明形状并适合多产品聚合，但需要复杂度预算、字段授权、N+1 和 Schema 治理。

RPC/IDL 提供强契约和高效生成，浏览器网关、可调试性和公开兼容需另行设计。

BFF 可以在外部暴露一种协议、向内部适配多种协议。

协议选择不能修复不清晰的领域边界。

同一组织允许不同域选择不同协议，但错误、身份、观测和版本政策应尽量一致。

## 10. 聚合、并发与部分失败

BFF 聚合先定义哪些数据阻断页面，哪些可以延迟、陈旧或缺省。

并行请求共享父 deadline，每个下游获得更短预算和可取消 signal。

不能在网关、BFF、SDK 和服务每层各重试三次。

只重试幂等且分类为临时失败的操作，并受 retry budget 限制。

可选模块失败时返回带 freshness/error 状态的局部结果，不伪造成功数据。

关键授权、价格和写操作失败时 fail closed。

错误响应要让 UI 决定重试、刷新、重新认证或人工处理。

## 11. 错误契约

统一 envelope 应包含稳定 code、用户可行动分类、request/trace id 和必要字段错误。

HTTP status 保留协议语义，不把所有失败包装成 200。

错误 message 不作为客户端分支依据，也不泄漏内部堆栈和敏感资源。

409、412、422、429、503 和 unknown side effect 应有不同恢复路径。

本地化在呈现层完成，服务端返回稳定机器码和安全参数。

新错误码对旧客户端要有 fallback 类别。

## 12. 分页、实时与 AI 流

大列表使用稳定 cursor 和确定排序，不让 BFF 把所有页读入内存再裁剪。

实时状态区分事件序号、快照、断线续传和最终权威读取。

SSE/WebSocket 只是传输，不能替代持久状态和恢复游标。

AI 输出区分增量文本、工具调用、审批、错误和最终完成事件。

客户端取消要传播到 BFF 和模型/下游，但已提交副作用仍需 reconciliation。

流式响应有最大时长、空闲超时、背压和连接容量预算。

## 13. 缓存与数据新鲜度

浏览器、BFF、CDN 和领域服务缓存必须使用一致的数据分类。

公开参考数据可共享缓存，个性化与授权数据默认私有。

BFF cache key 覆盖 tenant、principal scope、locale、实验和 Schema version。

缓存聚合结果会把多个上游新鲜度绑定在一起，常比逐域缓存更难失效。

响应可携带 freshness 和生成时间，让 UI 正确表达陈旧状态。

撤权、冻结和高风险动作不能依赖 stale allow。

## 14. 契约演进流程

新增 optional 字段通常容易，但新 enum 值也可能破坏穷尽分支。

类型改变、字段删除、语义改变和收紧输入通常需要新版本或双写迁移。

先让消费者容忍并读取新旧形式，再让生产者产生新形式，最后观测旧路径归零。

Schema diff 只能发现结构变化，consumer fixture 才能发现使用假设。

API 使用量按 client/release/version 观测，弃用基于真实流量而不是发布日期。

兼容层有 owner 和删除日期，避免永久双模型。

## 15. 平台与组织视角

API 平台提供 Schema registry、生成器、diff、mock、契约测试、错误规范和观测 SDK。

BFF 平台提供认证、deadline、限流、缓存、stream、审计和部署的安全默认值。

领域团队拥有业务 Schema 和兼容承诺；客户端团队拥有实际 consumer fixtures。

平台不自动生成业务聚合，也不替团队决定字段语义。

跨团队变更通过 RFC/ADR、弃用看板和迁移预算推进。

绕过平台的例外要有原因、owner、风险和到期日。

## 16. 失败模式与反花架子门槛

- 每个页面建一个 BFF endpoint，重复所有领域模型。
- 前端生成了类型，就不再验证网络数据。
- GraphQL endpoint 统一了入口，却没有字段授权和复杂度上限。
- 聚合请求无 deadline，一个慢服务拖死所有页面。
- BFF 为“体验”缓存权限 allow，撤权后继续放行。
- 服务端和客户端同时重试非幂等写，制造重复副作用。
- 错误都返回 200，UI 无法区分恢复动作。
- 弃用只发群通知，没有消费者和流量证据。

反花架子门槛：没有可测瀑布/安全/客户端差异，也没有长期 owner，就不新增 BFF 层。

## 17. 指标

- 核心页面请求数、瀑布深度、聚合 p50/p95 和下游占比。
- BFF 可用性、饱和度、超时、取消传播和局部降级成功率。
- 按 dependency 的错误、重试放大和 deadline 消耗。
- Schema breaking change 拦截、consumer fixture 覆盖和逃逸兼容事故。
- API 版本/字段使用、弃用完成时间和兼容层数量。
- runtime parse 失败、unknown error 和旧客户端 fallback。
- 缓存命中、错误命中、新鲜度和权限违规。
- 每个客户端端到端交付 lead time，而不是只看 endpoint 数量。

## 18. 架构评审清单

- 浏览器、BFF、Gateway 和领域服务各拥有什么责任？
- 不建 BFF 的方案为什么不能满足质量属性？
- principal/tenant 从哪里来，在哪些层重新授权？
- 聚合中哪些数据关键、可选、可 stale 或必须 fail closed？
- deadline、取消、重试和 unknown side effect 如何传播？
- DTO、领域模型和数据库模型是否分离？
- 类型生成之外，运行时 Schema 在哪里校验？
- 错误码是否稳定、可行动并向后兼容？
- Schema diff、consumer fixture 和生产流量如何共同治理？
- 流式连接如何恢复、背压和控制容量？
- 谁值班、谁迁移、何时删除兼容层？

## 官方延伸阅读

- [OpenAPI Specification](https://spec.openapis.org/oas/latest.html)
- [GraphQL Specification](https://spec.graphql.org/)
- [RFC 9457：Problem Details for HTTP APIs](https://www.rfc-editor.org/rfc/rfc9457)
- [Microsoft Azure：Backends for Frontends pattern](https://learn.microsoft.com/azure/architecture/patterns/backends-for-frontends)
- [OpenTelemetry HTTP Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/http/)
- [OWASP API Security Top 10](https://owasp.org/API-Security/)

## 现有 Master 交叉链接

- [JS 与浏览器第 11 章：Fetch、缓存、流与实时通信](../《JavaScript%20与浏览器高级学习问题》/11-Fetch缓存流与实时通信/00-讲义.md)
- [JS 与浏览器第 14 章：Web 安全与信任边界](../《JavaScript%20与浏览器高级学习问题》/14-Web安全与前端信任边界/00-讲义.md)
- [Backend Master 第 08 章：Session 与 OIDC](../Backend%20Master/08-身份认证Session与OIDC/00-讲义.md)
- [Backend Master 第 09 章：授权与多租户](../Backend%20Master/09-授权策略与多租户隔离/00-讲义.md)
- [Backend Master 第 10 章：API 契约演进与幂等](../Backend%20Master/10-API契约演进与幂等/00-讲义.md)
- [Backend Master 第 15 章：超时、重试与过载保护](../Backend%20Master/15-超时重试熔断隔舱与过载保护/00-讲义.md)
- [Backend Master 第 16 章：SSE 背压与断线恢复](../Backend%20Master/16-SSE实时事件背压与断线恢复/00-讲义.md)

## 本章结论

BFF 的价值是吸收客户端特有复杂度，而不是复制领域后端。

类型、Schema、错误、身份、deadline 和兼容共同组成契约，缺一项都可能让“统一接口”成为新风险。

先划责任，再选协议；先设计失败和演进，再生成客户端代码。
