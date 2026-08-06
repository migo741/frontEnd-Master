# 第 14 章参考答案

## 练习一：边界

```text
app/products/[id]/page.tsx             Server
├── ProductSummary                     Server
├── GalleryClient                      Client（只接收图片数据）
├── FavoriteButtonClient               Client（接收 productId/初始状态）
├── Suspense -> Recommendations         Server
└── Suspense -> Comments                Server
    └── CommentFormClient               Client
```

page 先创建 promise 而非串行 await：

```tsx
const productPromise = getProduct(id)
const recommendationsPromise = getRecommendations(id)
const product = await productPromise
if (!product) notFound()
```

推荐 Promise 传给相应 server child/边界等待。实际框架可能自动去重相同 fetch；复用一个 data access function 并用日志验证，不假设。

公开商品可按 tag `product:${id}` 缓存；推荐按商品/算法版本；评论短时或动态；收藏按 user+product 动态/私有，不能进入公共商品缓存。mutation 精确失效对应 tag。metadata 调用同一 getProduct，依赖 request memo/缓存去重。

用 bundle analyzer/search source map 验证 server-only key/module 未进入 client chunks；仅看页面能运行不够。Date.now 在服务器计算并作为稳定 prop 传入，或只在 hydration 后显示相对时间；不滥用 suppress。

## 练习二：根因与修复

模块级 `currentUser` 会被并发请求覆盖；`cache(getReport(id))` 把不同 tenant 同 id 合并，造成跨租户泄漏。身份从每次请求的可信 session 获取，数据函数签名显式：

```ts
getAuthorizedReport({actorId, tenantId, reportId})
```

先验证 actor 是 tenant 成员及 report 权限，再查数据；数据库查询自身包含 tenantId，不能查出后才在 JS 比较。缓存只用于授权后安全可共享的数据，key 至少 tenantId/reportId/version；若结果随用户权限/字段脱敏不同，再包含授权 variant 或不跨请求缓存。

Action 自身重复完整校验，忽略客户端传来的 actor/tenant 权威性；tenant 来自路由也要与 session membership 校验。CSV 大任务使用 operation id/idempotency key，审计 actor/tenant/report/result，不记录敏感 CSV 内容。

隔离测试并发发起 tenant A/report 1 与 tenant B/report 1，多轮交错，断言 payload、日志 context、cache hit 都不跨租户。测试生产缓存适配器，而非绕过缓存的 fake。

Runbook：订阅 React/框架公告 → SBOM/lockfile 搜索所有 `react-server-dom-*` 和框架 → 阻断新部署/应用临时 WAF 仅作缓解 → 升级官方列出的安全补丁 → RSC/Action 回归 + 安全扫描 → 小流量灰度监控异常请求/错误 → 全量并验证运行版本 → 清理缓解/复盘 MTTR。绝不把托管商临时缓解当最终修复。

