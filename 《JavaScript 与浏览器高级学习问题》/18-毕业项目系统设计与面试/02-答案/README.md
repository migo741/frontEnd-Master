# 第 18 章参考答案

毕业项目没有唯一代码答案。本章给一份可对照的参考架构与验收方法；如果你的方案满足约束且证据更好，不必改成相同库。

## 练习一参考架构

```text
Browser
├── Router / URL schema
├── React feature slices
│   ├── Ticket list (virtualized)
│   ├── Ticket editor (state machine)
│   └── AI assistant (stream state machine)
├── Server-state cache
├── Browser adapters
│   ├── IndexedDB outbox
│   ├── BroadcastChannel
│   ├── Worker query engine
│   └── Telemetry
└── BFF/API
    ├── authentication + authorization
    ├── idempotency + entity version
    ├── streaming gateway
    └── audit log
```

### 读写不变量

读：`route -> parse -> canonical query key -> request/cache -> immutable snapshot -> UI`。任何不可解析参数回到明确默认或错误页，不让无效 URL 进入深层组件。

写：`intent -> local validation -> mutationId/baseVersion -> optimistic layer/outbox -> server auth -> authoritative version -> reconcile`。旧响应只确认自己的 mutation；服务端用 baseVersion/ETag 和幂等键阻止旧写。

离线 outbox 记录示例：

```js
{
  id: crypto.randomUUID(),
  entityId,
  baseVersion,
  operation: 'ticket.patch',
  payload,
  status: 'queued',
  createdAt,
  attempts: 0,
}
```

恢复时按实体顺序或领域规则发送，不盲目全并发；409 进入 `conflicted`，让用户看到本地/服务端差异。BroadcastChannel 只通知“某实体 version 已变”，权威数据仍从缓存/API 读取。

### 性能证据

- 用真实规模 fixture，而不是 20 行 demo；
- Worker 只做纯计算，结果以 generation 守门；
- 虚拟化限制 DOM，但保留焦点/语义和稳定 key；
- 推送合并到有限频率，后台事件不得无限排队；
- 报告至少包含设备/网络、三次以上样本、p50/p75、主线程轨道和 React commit；
- 三快照法证明重复开关详情后 heap 回稳。

### 安全证据

威胁模型至少覆盖：存储型 DOM XSS、Cookie CSRF、越权批量操作、跨窗口伪消息、日志泄密、依赖/AI 输出。CSP/Trusted Types 是 XSS 纵深层；服务端权限和 schema 验证不由前端替代。

### 测试分层

- reducer/parser/LRU/协议：单元和属性测试；
- 编辑器 + mock transport/IndexedDB：集成测试，主动反转响应；
- 登录、筛选、编辑、离线恢复、冲突：少量 E2E；
- API/stream/message：契约测试；
- 性能、axe、依赖/安全：独立门禁或发布检查。

### 观测与发布

每条关键操作关联 releaseId/sessionId/requestId/entityId(非敏感)；上报分类结果和时长，不上传正文。灰度 dashboard 至少看启动成功率、关键旅程成功率、INP、JS error、冲突率、outbox 堆积与 AI 流失败率。

静态资源内容哈希，HTML 更新策略明确；API 至少跨灰度窗口向后兼容；feature flag 有 kill switch。回滚演练必须在旧 SW/缓存 cohort 上做一次。

## 练习二答题框架

无论抽到哪个变更，都按相同顺序：

1. 写受影响不变量；
2. 标出新的数据/信任/线程边界；
3. 定义状态和事件，不先堆 if；
4. 先写一个能失败的测试或基准；
5. 实现最小正确路径；
6. 注入取消、迟到、离线、重复或恶意输入；
7. 记录证据、剩余风险和发布策略。

例如“推送 500/s”：不要把 500 次事件直接 setState。按实体合并最新 version，建立有界缓冲；Worker 做可并行归并时使用 transfer/代次；每帧或固定窗口发布一个不可变 snapshot；视图只渲染可见区域。测试队列不会无界、最终状态与顺序规则一致，并用 Performance 证明输入延迟。

例如“AI tool call”：流事件先过 schema/状态机，模型无权直接调用高风险接口；UI 展示参数与证据，用户确认后由服务端再次鉴权并用幂等键执行，审计包含模型建议、人工确认、实际结果。提示词不是安全边界。

## 最终自评

逐项使用第 18 章 100 分表评分。任何一项只有“我用了某库”而没有测试、profile、威胁模型或运行证据，最多给该小项一半分。

答辩最后应能用一句话总结：

> 我没有试图证明这个项目永不失败；我定义了它必须守住的不变量、可接受的性能和错误预算，并用测试、运行时观测、灰度和回滚让失败可发现、可限制、可恢复。

复写任务：关闭答案，画出你自己的读路径、写路径、离线路径和故障路径；若四张图里同一份状态有四个不同所有者，回到架构重构。

