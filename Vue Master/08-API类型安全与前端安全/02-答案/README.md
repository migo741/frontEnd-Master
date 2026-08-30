# 答案与复盘

## 题 1

```ts
let refreshFlight: Promise<void> | undefined

async function request(input: RequestInfo, init: RequestInit & { retried?: boolean } = {}) {
  const response = await rawFetch(input, init)
  if (response.status !== 401 || init.retried || isRefreshUrl(input)) return parse(response)

  refreshFlight ??= refreshToken().finally(() => { refreshFlight = undefined })
  try {
    await refreshFlight
  } catch (error) {
    authEvents.expireOnce()
    throw new AuthExpiredError({ cause: error, requestId: readRequestId(response) })
  }
  if (init.signal?.aborted) throw init.signal.reason
  return request(input, { ...init, retried: true })
}
```

核心测试：并发 401 的 refresh 调用数为 1；刷新成功全部重放；刷新失败 logout 事件一次；重放再 401 不再刷新；等待 refresh 期间某调用者 abort 时不重放。生产中还要防“旧 refresh finally 清掉新 flight”，最简单是保持严格 single-flight，或只在 identity 相等时清理。

## 题 2

数据流应为 Markdown 源文本 → 禁止/转义原始 HTML 的 parser → 生成 HTML → 服务器和客户端统一 sanitizer allowlist → `v-html` 渲染。链接协议只允许 http/https/mailto 等，外链增加合适 rel；代码块内容必须按文本处理。存储源 Markdown 便于规则升级后重新生成，缓存的 HTML 带 sanitizer version。

CSP 禁止 inline script 并限制 script-src，降低漏网 XSS 的影响但不替代 sanitizer。管理员预览同样是不可信输入，不能因为“管理员页面”降低防护；持久型 XSS 对管理员反而更危险。测试使用事件属性、SVG、畸形标签、编码后的 javascript URL 和 target blank 场景。最终授权仍在服务端，富文本权限不能靠前端隐藏。

