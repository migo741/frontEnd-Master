# 第 14 章练习

## 练习一：Server/Client 边界瘦身

给一个 Next App Router 商品页：顶部 `page.tsx` 写了 `'use client'`，包含商品查询、SEO metadata、轮播、收藏按钮、推荐、评论表单，客户端 bundle 很大且首屏瀑布。

任务：

- 把 page/layout/data fetch 改为 Server Components，交互叶子（轮播、收藏、表单）保留 Client。
- 并行启动商品/推荐；评论可流式后 reveal；404 用 `notFound` 类语义。
- server-only API key 不进入 bundle；用工具验证。
- 设计每类数据的缓存/失效；用户收藏不得公共缓存串用户。
- metadata 基于服务器商品数据，避免重复请求。
- 对比 before/after 客户端 JS、瀑布、LCP/TTFB；记录服务器成本。
- 制造并修复一个 `Date.now()` hydration mismatch。

## 练习二：多租户缓存与 Server Action 安全审计（高难）

SaaS 路由 `/[tenant]/reports/[id]`，不同租户可能有相同 report id。开发者写了模块级 `currentUser` 和 `cache(getReport(id))`；导出 CSV 的 Server Action 只检查前端是否显示按钮。

任务：

- 找出用户/租户串数据路径，给 request scope 与 cache key 设计。
- Server Action 重做身份、tenant membership、report permission、schema、速率/审计、幂等（若生成任务）。
- 定义 CDN/应用缓存 headers 和 invalidation；证明 private payload 不公共缓存。
- 添加两个并发用户/同 id 不同 tenant 的隔离测试。
- 写 RSC 漏洞响应 runbook：发现公告 → 资产盘点 → 补丁/缓解 → 测试 → 灰度 → 验证。

交付威胁模型：资产、入口、信任边界、攻击者能力、缓解、残余风险。

