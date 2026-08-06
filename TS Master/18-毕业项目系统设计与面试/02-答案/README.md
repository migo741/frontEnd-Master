# 第 18 章参考答案与验收标准

## 练习一：参考架构

依赖方向应单向：domain/schema → protocol → sdk-core → adapters/apps；testing 可依赖公共协议并向消费者提供 fake transport，但生产 core 不依赖 testing。endpoint definition 保存 Schema 值，静态输出从 Schema 推断；transport 只返回 unknown response，protocol 层解析并分类错误。

最低可接受实现：

- `request(endpoint, input, options)` 从 endpoint 推断，不暴露返回泛型。
- `Result` 业务错误可穷尽；network/http/protocol/aborted 分类明确。
- stream parser 正确处理 UTF-8/半行/坏行/上限/cleanup。
- cache key 包含 endpoint 和规范化 input；adapter cleanup 防旧请求回写。
- versioned event 先 Schema parse，再逐版 migrate 到 current domain event。
- package exports、declarations 与 tarball fixture 一致。
- typecheck/runtime/e2e/performance matrix 可一键复现。

不要求自研完整 Schema 库；可选择成熟库，但要在 ADR 说明依赖、bundle、错误格式和版本锁定。重要的是边界只验证一次、类型从真实 validator 推断，不复制两份 DTO。

## 评分表（100 分）

- 运行时边界与错误模型：20
- 领域类型与非法状态排除：15
- 泛型 API 推断和错误可读性：15
- 异步取消、流与资源清理：10
- 模块发布和 consumer fixtures：10
- Monorepo/性能与环境隔离：10
- 类型/runtime/e2e 测试设计：10
- ADR、升级治理和讲解能力：10

任一“一票否决”：把外部 JSON 直接断言成领域类型；核心大量 any；包无法从 tarball 消费；取消后仍稳定回写旧状态；声明与 runtime 入口不一致。

## 练习二：评审 rubric

优秀回答不会只列名词。以 generic fetch 为例：应指出调用者选择 T 与 URL/runtime 无证据关系，给出恶意响应失败路径，再提出 endpoint-owned Schema，并设计正负类型测试和坏响应 runtime test。

性能题先要求 config、版本、冷/热场景和 diagnostics/trace，不凭类型外观猜；优化后用相同 fixture 对比。升级题要有稳定 TS 6 车道、TS 7 non-blocking 矩阵、compiler API 工具盘点、退出门槛和回滚条件。

## 面试题答题骨架示例

“为什么不用 `as User`？”不是因为断言语法永远错误，而是它不执行验证。若值来自网络，最小失败例是 `{id: null}` 仍被视为 User；应以 unknown 接收、Schema 验证、失败进入 protocol error。若值刚经过 DOM tag check 等 runtime 证明，局部断言可能合理，并由测试保护。

“为什么放弃精确类型？”例如 1,200 路由的两两许可会导致二次组合实例化。保留 route→params 的按 key 精确映射，把全部转移许可移到生成的 runtime adjacency Map，可换取数量级性能和清楚错误，同时不牺牲调用端最重要的参数安全。

## 最终复盘

完成后写一页复盘：最初误判、最危险边界、一次类型精度取舍、性能证据、若团队扩大十倍如何演进。能诚实解释限制并给验证路线，才是真正可用于大厂项目的高级能力。
