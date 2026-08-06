# 第 18 章练习

## 练习一：完成毕业项目（必做）

### 功能验收

- [ ] 多租户路由、会话和服务端资源级权限；两个 tenant 同 id 不串数据。
- [ ] 工单列表 URL 可分享，loader/query 无双请求，快速筛选无旧响应。
- [ ] 编辑表单可访问，服务端校验，409 版本冲突可恢复，关键 mutation 幂等。
- [ ] 实时事件有 sequence/dedupe/reconnect/snapshot；WebSocket 实例不进 store。
- [ ] AI 流有半包 parser、32ms 左右批量、stop/retry、工具确认、Markdown 净化。
- [ ] 错误边界与故障域匹配；关键错误有 trace id 和恢复动作。
- [ ] 测试覆盖最危险路径；Playwright 至少 3 条稳定 E2E。
- [ ] 键盘、焦点、屏幕阅读器基本验收；自动 axe 只作辅助。
- [ ] performance/bundle/DOM 预算；保存 before/after profile。
- [ ] RSC 路线使用当前安全补丁并完成版本审计；SPA 路线写 SSR/RSC 选型 ADR。

### 文档验收

```text
docs/
├── REQUIREMENTS.md
├── ARCHITECTURE.md
├── THREAT-MODEL.md
├── TEST-STRATEGY.md
├── PERFORMANCE.md
├── OBSERVABILITY.md
├── RELEASE-RUNBOOK.md
├── INCIDENT-REVIEW.md
└── adr/0001-....md
```

### 演示验收

演示不是只走 happy path。15 分钟内展示：正常流程、一个竞态、一个权限拒绝、一个断线恢复、一次性能证据和一次回滚。

## 练习二：90 分钟模拟大厂面试（高难）

### 30 分钟系统设计

题目：设计“10 万行实时风控告警平台”，支持筛选/分组、多人处理、AI 摘要、权限、多租户、99.9% 可用。

要求主动澄清：告警率/峰值、延迟、设备、数据保留、权限、SEO、团队、离线、合规。画加载/实时/错误/缓存边界，给容量和降级。

### 35 分钟代码

实现 `useLatestRequest(key, fetcher)`：只暴露最新 key 结果，支持取消、retry、判别状态、StrictMode；再写一个竞态测试。最后说明为什么生产更可能用 Query/loader。

### 25 分钟深挖

从上章 18 题随机抽 6 题，每题 3 分钟回答，面试官连续追问失败模式和证据。录音后逐句删掉“应该、可能、反正”，改为约束明确的表达。

## 自评分（每项 0–4）

- React 心智模型与原理
- TypeScript/状态建模
- 数据/并发/错误处理
- 性能证据
- 测试可靠性
- 架构与工程化
- SSR/RSC/安全
- a11y/observability
- 沟通与业务权衡

总分 36：28+ 且无单项低于 2，才进入真实面试投递；不足项回到对应章节重做第二题。

