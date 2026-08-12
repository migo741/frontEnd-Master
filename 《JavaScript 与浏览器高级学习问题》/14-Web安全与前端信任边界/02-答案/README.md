# 第 14 章参考答案

## 练习一

因果链：不可信 Markdown 先被插件转成字符串，再进入 `innerHTML`；React/Vue 或 Markdown 本身都不会自动保证第三方插件输出安全。URL sink 又有独立协议风险，HTML sanitizer 不能替代 URL allowlist。

参考边界：

```js
const ALLOWED_PROTOCOLS = new Set(['https:', 'http:'])

export function safeExternalUrl(raw, base = location.origin) {
  const url = new URL(raw, base)
  if (!ALLOWED_PROTOCOLS.has(url.protocol)) throw new TypeError('Unsupported URL protocol')
  return url.href
}

export function renderPreview(markdown) {
  const dirty = renderMarkdown(markdown)
  const clean = DOMPurify.sanitize(dirty, {
    ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'code', 'pre', 'a', 'ul', 'ol', 'li'],
    ALLOWED_ATTR: ['href', 'title'],
    ALLOW_UNKNOWN_PROTOCOLS: false,
  })
  return clean
}
```

真正项目还应给所有外链统一加安全属性，并在 sanitizer hook 中重新解析 URL。不要把 `DOMPurify` 名字当作免审：依赖版本、配置和 DOM clobbering 等边界都要跟踪。

Trusted Types 可把唯一 sink 收拢：

```js
const policy = globalThis.trustedTypes?.createPolicy('app-html', {
  createHTML: input => renderPreview(input),
})

preview.innerHTML = policy ? policy.createHTML(markdown) : renderPreview(markdown)
profileLink.href = safeExternalUrl(user.profileUrl)
```

上线顺序：

1. 建立 CSP 基线与唯一 nonce 生成链；
2. `Content-Security-Policy-Report-Only` 收集真实违规，去掉 inline/eval；
3. 在采样与聚合后处理浏览器扩展噪声；
4. 小流量强制 CSP，保留可快速回滚的响应头配置；
5. Trusted Types 也先 report-only，限制 policy 名称和创建模块；
6. 将违规率、页面失败率和 sanitizer 拒绝计数接入发布观察。

核心测试表：

| 输入 | 预期 |
|---|---|
| `**ok**` | 保留 `strong` |
| `<img src=x onerror=...>` | 标签/事件属性不进入 DOM |
| `[x](javascript:...)` | 链接被移除或拒绝 |
| 混淆大小写/控制字符协议 | 仍拒绝 |
| 普通中文与 emoji | 内容无损 |
| 超大输入 | 在业务层被限长 |

## 练习二

安全协议不相信 iframe 的业务结论，只相信它来自预期窗口和源、属于当前会话，并把它当作触发后端确认的信号。

```js
const PAY_ORIGIN = 'https://pay.example-pay.cn'
const MAX_AGE_MS = 5 * 60_000
const ORDER_STATES = new Set(['pending', 'paid', 'failed', 'cancelled'])

function parseAuthoritativeOrder(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value) ||
      !ORDER_STATES.has(value.status)) {
    throw new TypeError('Invalid authoritative order response')
  }
  return {status: value.status}
}

async function confirmOrderFromServer(orderId, {signal}) {
  const response = await fetch(`/api/orders/${encodeURIComponent(orderId)}`, {
    credentials: 'same-origin',
    headers: {'Accept': 'application/json'},
    signal,
  })
  if (!response.ok) throw new Error(`Order confirmation failed: HTTP ${response.status}`)
  let value
  try {
    value = await response.json()
  } catch (cause) {
    throw new SyntaxError('Order confirmation returned invalid JSON', {cause})
  }
  return parseAuthoritativeOrder(value)
}

export function createPaymentProtocol({
  frame,
  eventTarget = window,
  payOrigin = PAY_ORIGIN,
  maxAgeMs = MAX_AGE_MS,
  now = Date.now,
  setTimer = setTimeout,
  clearTimer = clearTimeout,
  confirmOrder = confirmOrderFromServer,
  writeState = () => {}, // 生产中传入 store/sessionStorage 的受控写入函数
  countInvalidMessage = () => {},
  reportError = () => {},
  showSuccess = () => {},
  showPendingOrFailure = () => {},
  showConfirmationError = () => {},
}) {
  if (!frame || typeof eventTarget?.addEventListener !== 'function') {
    throw new TypeError('frame and eventTarget are required')
  }
  if (!Number.isFinite(maxAgeMs) || maxAgeMs <= 0) {
    throw new RangeError('maxAgeMs must be positive')
  }

  let active = null
  let disposed = false
  let state = Object.freeze({status: 'idle', updatedAt: now()})

  const safely = (callback, ...args) => {
    try {
      callback(...args)
    } catch (error) {
      if (callback !== reportError) {
        try { reportError(error) } catch {}
      }
    }
  }

  const publish = (current, status, detail = {}) => {
    if (current) current.status = status
    // nonce、seen 和 AbortController 都不能进入持久化/UI 状态。
    state = Object.freeze(current ? {
      status,
      requestId: current.requestId,
      orderId: current.orderId,
      startedAt: current.startedAt,
      updatedAt: now(),
      ...detail,
    } : {status, updatedAt: now(), ...detail})
    safely(writeState, state)
  }

  const finish = (current, status, detail, reason) => {
    // timeout、cancel、dispose、确认结果只能有一个赢得终态。
    if (active !== current) return false
    if (current.timer !== null) {
      clearTimer(current.timer)
      current.timer = null
    }
    if (!current.controller.signal.aborted) current.controller.abort(reason)
    active = null
    publish(current, status, detail)
    return true
  }

  const expire = current => finish(
    current,
    'timed-out',
    {reason: 'timeout'},
    new DOMException('Payment session timed out', 'TimeoutError'),
  )

  const cancelSession = (current, reason = 'user') => finish(
    current,
    'cancelled',
    {reason: typeof reason === 'string' ? reason : 'cancelled'},
    reason,
  )

  const handleMessage = async event => {
    if (disposed || event.origin !== payOrigin) return
    const current = active
    if (!current || event.source !== current.source) return

    let message
    try {
      message = parsePaymentMessage(event.data) // 普通对象、大小、版本、枚举与 UUID
    } catch (error) {
      safely(countInvalidMessage, error)
      return
    }

    if (active !== current || message.requestId !== current.requestId ||
        message.nonce !== current.nonce) return
    // 后台页 timer 可能被节流，因此接收消息时还要同步校验年龄。
    if (now() - current.startedAt >= maxAgeMs) {
      expire(current)
      return
    }
    if (message.type !== 'payment.hint' || current.status !== 'pending') return
    if (current.seen.has(message.eventId) || current.seen.size >= 32) return
    current.seen.add(message.eventId)

    // 在第一个 await 之前落地 confirming，阻止不同 eventId 的并发确认。
    publish(current, 'confirming')
    if (active !== current) return

    try {
      const raw = await confirmOrder(current.orderId, {signal: current.controller.signal})
      const authoritative = parseAuthoritativeOrder(raw) // 自定义 confirmOrder 也不能绕过 schema
      // await 期间可能 begin B、timeout、cancel 或 dispose；A 不得写入 B 的 UI。
      if (active !== current || current.status !== 'confirming' ||
          current.controller.signal.aborted) return
      if (authoritative.status === 'paid') {
        if (finish(current, 'paid', {}, new DOMException('Confirmed', 'AbortError'))) {
          safely(showSuccess, current.orderId)
        }
      } else if (finish(
        current,
        'pending-result',
        {authoritativeStatus: authoritative.status},
        new DOMException('Confirmation completed', 'AbortError'),
      )) {
        safely(showPendingOrFailure, authoritative.status, current.orderId)
      }
    } catch (error) {
      // 被 B/timeout/cancel/dispose 终止的 A 只安静退出，不落失败状态。
      if (active !== current || current.status !== 'confirming' ||
          current.controller.signal.aborted) return
      if (finish(current, 'confirmation-failed', {
        errorName: error?.name ?? 'Error',
      }, error)) {
        safely(showConfirmationError, current.orderId, error)
      }
    }
  }

  const onMessage = event => {
    // 无论 parser、确认器还是内部回调怎样失败，都不能制造 unhandled rejection。
    void handleMessage(event).catch(error => safely(reportError, error))
  }
  eventTarget.addEventListener('message', onMessage)

  return {
    beginPayment(orderId) {
      if (disposed) throw new DOMException('Payment protocol disposed', 'InvalidStateError')
      if (typeof orderId !== 'string' || orderId.length === 0 || orderId.length > 128) {
        throw new TypeError('Invalid orderId')
      }
      const source = frame.contentWindow
      if (!source) throw new DOMException('Payment frame is unavailable', 'InvalidStateError')

      if (active) cancelSession(active, 'superseded')
      const current = {
        requestId: crypto.randomUUID(),
        nonce: crypto.randomUUID(),
        orderId,
        source,
        startedAt: now(),
        seen: new Set(),
        status: 'pending',
        timer: null,
        controller: new AbortController(),
      }
      active = current
      publish(current, 'pending')

      try {
        // 这是真实 timeout；年龄检查只是浏览器节流下的第二道保险。
        current.timer = setTimer(() => expire(current), maxAgeMs)
        source.postMessage({
          version: 1,
          type: 'payment.start',
          requestId: current.requestId,
          nonce: current.nonce,
          orderId,
        }, payOrigin)
      } catch (error) {
        finish(current, 'protocol-error', {errorName: error?.name ?? 'Error'}, error)
        throw error
      }

      return Object.freeze({
        requestId: current.requestId,
        cancel: reason => cancelSession(current, reason),
      })
    },

    cancel(reason = 'user') {
      return active ? cancelSession(active, reason) : false
    },

    getState() {
      return state
    },

    dispose() {
      if (disposed) return false
      disposed = true
      eventTarget.removeEventListener('message', onMessage)
      if (active) {
        finish(
          active,
          'disposed',
          {},
          new DOMException('Payment protocol disposed', 'AbortError'),
        )
      } else {
        publish(null, 'disposed')
      }
      return true
    },
  }
}
```

`parsePaymentMessage` 应拒绝非普通对象、额外巨大字段、未知版本/类型、非法 UUID 和非预期枚举。消息解析、响应 JSON 解析和响应 schema 校验分别被捕获；监听器最外层还收口意外 Promise rejection。`writeState` 必须接到应用 store 或受控 sessionStorage，参考快照故意不落 nonce。frame 发生 `load` 后还要确认其目标 URL/当前会话策略；跨源页面无法读取其实际 location，因此协议超时与后端状态是最终保险。

至少测试：恶意相似域名、正确 origin 但错误 window、错误 nonce、重复 eventId、不同 eventId 的并发 hint、格式炸弹及 parser 抛错。用 fake timer 推进到 maxAgeMs，断言状态落为 `timed-out`、确认 fetch 被 abort、迟到 paid 不展示成功；用户 cancel 与 dispose 都清 timer、落状态且二次调用幂等。让响应 JSON 与 schema 分别失败，断言进入 `confirmation-failed` 且没有 unhandled rejection。A 确认期间开始 B，随后按 A 成功/B 成功、B 成功/A 失败等顺序完成，只有 B 可落 UI；让 timeout/cancel 与 paid 在相邻 tick 竞争，断言只产生一个终态。还要覆盖 postMessage 同步失败、后端仍未支付和 writeState 回调失败。真正的资产（订单状态）由后端鉴权和支付渠道回调保护。

复写任务：关闭答案，只保留消息 schema 和威胁模型，从空文件实现接收端；每个 `return` 旁写明挡住哪种攻击。
