# 第 12 章练习：把 SSR 的边界做对

> 本章恰好两题。每题都要求写“数据属于谁、在哪运行、如何序列化、怎样缓存、失败如何验证”。

## 题 1：修复跨租户泄漏与 Hydration Mismatch

### 背景

团队手写了 Vue 3.5 SSR。当前代码在模块顶层创建 `reactive({ user: null, now: Date.now() })` 和 router；请求到达后写入当前用户，再 `renderToString(app)`。页面模板使用 `Math.random()` 生成 input id，并按服务器本地时区格式化订单时间。浏览器启动时重新请求 profile，然后 `createApp()` 挂载。

压测中，租户 A 偶尔在 HTML 里看见租户 B 的名称；浏览器有 mismatch，profile 请求两次。团队想用 `data-allow-mismatch` 和 CDN `public, max-age=60` 快速止血。

### 交付物

1. 画出请求 A/B 污染与服务端/客户端不一致的因果链。
2. 用 strict TypeScript 写出最小 `createApp(requestContext)`、server entry、client entry 和安全状态传输接口；可省略 HTTP 框架胶水，但不可省略每请求 app/router/store。
3. 设计确定性 id、时间与 locale 策略；说明哪些数据可以进入 payload，哪些绝不能进入。
4. 给出 HTML、payload、API 的缓存头/缓存 key；明确为什么不能把个性化 HTML public cache。
5. 写至少五个测试，其中必须包含两个并发用户、无重复首次取数、无 hydration 警告、真实 404/status 和恶意序列化字符串。
6. 写出最小止血、长期修复与回滚信号。

### 约束

- 不能只靠 suppress mismatch；
- 不能把 token 或完整 server session 序列化到页面；
- 不能用“SSR 全关掉”作为唯一答案；
- 状态序列化必须使用安全通道，不得字符串拼接用户输入。

### 发散追问

如果订单时间必须在首屏按用户时区展示，但首次请求中没有时区，你如何在“无 mismatch、无 CLS、首屏有意义”之间做产品选择？

## 题 2：为 Nuxt 4 SaaS 设计混合渲染与数据边界

### 背景

同一 Nuxt 4 应用包含：

- `/` 与 `/pricing`：公共营销页，每周修改；
- `/docs/**`：10,000 篇公共文档，分钟级更新；
- `/catalog/:slug`：公共商品，价格 30 秒内可陈旧，库存要求更实时；
- `/dashboard/**`：登录后的租户数据；
- `/editor/**`：依赖浏览器 Canvas 的 2MB 编辑器；
- `server/api/report`：用服务凭证访问内部报表服务。

现状是所有路由统一 SSR，页面 setup 直接 `$fetch`，模块级 `ref` 保存 tenant，CDN 对所有 HTML 缓存 5 分钟。

### 交付物

1. 为每类路由选择 prerender、SSR/SWR、CSR/client-only、Node 或 edge，写决策矩阵和反例。
2. 给出 `routeRules` 概念配置，并为价格、库存、dashboard 分别定义缓存身份、TTL/失效与 header。
3. 写一个使用 `useFetch` 或 `useAsyncData` 的商品页；价格可复用 payload，库存能在客户端刷新，key 必须稳定。
4. 写一个 `useState` 租户状态，并解释 request isolation 与 payload 可见性。
5. 为 Nitro report route 写身份、对象权限、输入 schema、私有 runtime config、上游 timeout、DTO 裁剪与错误映射骨架。
6. 设计 SEO、无 JS、hydration、缓存串租户、边缘兼容与 observability 测试。

### 约束

- 商品价格与库存不可因一个全页面 TTL 被强行绑在一起；
- 客户端 runtime config 不得包含服务凭证；
- editor 即使 CSR，也要有可理解的服务端 fallback 与错误路径；
- 必须说明 Edge 不适用时如何退回 Node。

### 发散追问

产品希望 dashboard 也能从 CDN 秒开。你会缓存 shell、缓存用户片段，还是使用边缘个性化？列出安全证明和运行成本后再决策。
