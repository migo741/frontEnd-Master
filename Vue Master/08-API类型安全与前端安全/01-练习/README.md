# 第 08 章练习：可信 API 边界与认证收敛

> 只做两题。题 1 把 `unknown` 变成可用领域数据；题 2 把认证竞态和 Web 安全放进真实上传/富文本场景。

## 题 1：实现 schema-first 的最小 API Client（机制题）

### 背景

团队当前的封装是：

```ts
async function get<T>(url: string): Promise<T> {
  return fetch(url).then(response => response.json())
}
```

它不能处理 204、非 2xx、错误 JSON、运行时 schema、timeout、调用方 Abort、request ID 或幂等键。

### 契约

实现：

```ts
interface ApiClient {
  request<T>(path: string, options: RequestOptions<T>): Promise<T>
}
```

`RequestOptions<T>` 至少含：method、query、JSON body 或 FormData（二者互斥）、headers、decoder、caller signal、timeout、credentials、idempotency key。错误必须归一成 discriminated union，至少区分：

- aborted；
- timeout；
- network；
- HTTP unknown error；
- 已验证 problem detail；
- response validation failure。

实现一个 `TicketRepository.getById`，完成 `TicketDto -> Ticket domain` 映射。

### 规模与限制

- 浏览器支持标准 `fetch`；可自己实现 signal 合并；
- 单响应最多解析 1 MB JSON，超过即拒绝或说明由网关限制；
- 所有 endpoint 都基于固定 `API_BASE_URL`，path 不允许变成任意外部 origin；
- strict TypeScript，不允许 `response.json() as T`；
- 不依赖具体 schema 库也可以，但测试必须证明 decoder 真执行；
- FormData 时不得手写 multipart `Content-Type`。

### 失败语义

- caller abort：抛 `kind: aborted`，不进入重试和 toast；
- timeout：抛 `kind: timeout`，写请求 UI 显示“结果未知”而非“肯定失败”；
- 2xx 但 schema 错：抛 validation 并带脱敏 issues；
- 404 problem：保留稳定 `code/status/requestId`；
- 错误体是 HTML 或非法 JSON：仍能归一为 HTTP error；
- decoder 抛异常：不得伪装成网络错误。

### 验收

- [ ] `fetch` 的 `response.ok` 被显式检查；
- [ ] 204/JSON/problem/non-JSON 分支可测；
- [ ] timeout 和 caller abort 可区分且清 timer/listener；
- [ ] URL 用 `URL/URLSearchParams`，不拼接用户输入；
- [ ] DTO 与 domain 分层；
- [ ] request ID 被保留但敏感 body 不进日志；
- [ ] POST 自动重试前必须有幂等契约；
- [ ] 至少 8 个 Vitest/MSW 测试场景。

### 发散

- OpenAPI 生成的 TypeScript 类型、生成的 runtime validator、手写 domain mapper 应分别放在哪层？
- 当响应非常大时，为什么 `Content-Length` 检查仍可能不够？

---

## 题 2：并发 401、富文本与分片上传的生产防线（生产开放题）

### 背景

一个知识库页面加载正文、评论、权限、附件列表，4 个请求可能同时返回 401。用户还能编辑富文本并上传 2GB 视频到对象存储。系统使用 HttpOnly session cookie；`/auth/refresh` 可恢复会话。上传使用服务端签发的短期分片 URL。

### 契约

设计并实现核心部分：

1. `refreshOnce()`：并发 401 共享一次 refresh；
2. 每个原请求最多 replay 一次，refresh 请求不进入自身拦截器；
3. logout 与 refresh 使用 `authEpoch` 或等价机制解决竞态；
4. refresh 失败只清会话、清敏感缓存、通知 UI 一次；
5. 富文本展示的 sanitizer 信任边界、URL scheme 白名单与 CSP 协作；
6. Cookie 认证下的 CSRF 防线；
7. 分片上传状态机、并发上限、checksum、暂停/继续/取消/完成；
8. 客户端与服务端分别验证什么；
9. 下载附件时验证 content-type、清理 Object URL、安全文件名。

### 规模与限制

- 20 个并发 API 请求；
- refresh p95 600ms，只允许同一时刻 1 次；
- 2GB 文件，分片 8~32MB，并发最多 4；
- 页面切换可取消上传，但已传分片可能留在服务端；
- 不把 session credential、对象存储密钥或完整富文本写入日志；
- 不允许用正则自制 HTML sanitizer；
- 前端校验不能被写成最终安全边界。

### 失败语义

| 场景 | 期望 |
|---|---|
| 20 个请求同时 401 | 一次 refresh，各请求最多重放一次 |
| refresh 期间 logout | refresh 完成也不得恢复旧会话 |
| refresh 401/403 | 统一变 anonymous，只触发一次登录提示 |
| 非幂等 POST 收到 401 | 未知执行状态时不得盲重放 |
| 某上传 part 失败 | 有界重试；已成功 part 不重复或幂等 |
| 完成提交超时 | 用 uploadId 查询最终状态，不重新创建 |
| sanitizer 拒绝内容 | 安全纯文本/错误态，不回退原始 `v-html` |

### 验收

- [ ] 有可控制 Promise 的 20 并发 401 测试；
- [ ] 有 logout-refresh race 测试；
- [ ] 明确区分可重放与不可安全重放请求；
- [ ] CSRF、XSS、CSP、CORS 的职责没有混淆；
- [ ] 上传状态是有限状态机，不是一组互相矛盾 boolean；
- [ ] 服务端会验证权限、大小、内容、checksum、配额、uploadId；
- [ ] 取消后有 abort/过期回收协议；
- [ ] 至少列出 6 个恶意/异常测试样本。

### 发散

- 如果改用 access token + refresh token，存储位置的 XSS/CSRF 权衡如何变化？
- 富文本需要嵌入视频、iframe 时，怎样把允许能力限制到最小？
