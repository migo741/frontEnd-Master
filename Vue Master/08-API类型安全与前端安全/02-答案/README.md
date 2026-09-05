# 第 08 章答案：边界可靠性不是泛型幻觉

## 题 1 参考答案：让 `unknown` 经过 decoder

### 1. 类型契约

```ts
export interface ValidationIssue {
  path: string
  message: string
}

export interface Decoder<T> {
  decode(input: unknown):
    | { ok: true; value: T }
    | { ok: false; issues: readonly ValidationIssue[] }
}

interface ProblemDetail {
  type?: string
  title: string
  status: number
  code: string
  detail?: string
  requestId?: string
  fields?: readonly { field: string; code: string; message: string }[]
}

export type ApiError =
  | { kind: 'aborted'; reason?: unknown }
  | { kind: 'timeout'; timeoutMs: number }
  | { kind: 'network'; cause: unknown }
  | { kind: 'http'; status: number; requestId?: string; body?: unknown }
  | { kind: 'problem'; problem: ProblemDetail }
  | { kind: 'validation'; issues: readonly ValidationIssue[]; sample?: unknown }

export class ApiFailure extends Error {
  constructor(readonly detail: ApiError) {
    super(detail.kind)
    this.name = 'ApiFailure'
  }
}

type BodyOptions =
  | { json?: never; form?: never }
  | { json: unknown; form?: never }
  | { json?: never; form: FormData }

export type RequestOptions<T> = BodyOptions & {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  query?: Readonly<Record<string, string | number | boolean | null | undefined>>
  headers?: HeadersInit
  credentials?: RequestCredentials
  signal?: AbortSignal
  timeoutMs?: number
  decoder: Decoder<T>
  idempotencyKey?: string
}
```

`BodyOptions` 用 union 在编译期禁止 JSON 与 FormData 同时出现。decoder 返回结果而不是直接抛异常，能保留结构化 issues；若第三方 schema 库会抛，adapter 应在边界捕获并转成此协议。

### 2. 基础工具

```ts
const MAX_JSON_CHARS = 1_000_000

function makeUrl(
  baseUrl: URL,
  path: string,
  query: RequestOptions<unknown>['query'],
): URL {
  if (path.startsWith('/') || path.startsWith('//') || /^[a-z][a-z0-9+.-]*:/i.test(path)) {
    throw new TypeError('API path must be relative to configured base URL')
  }
  // 禁止 //evil.test 或绝对外链借 base 跳 origin。
  const url = new URL(path, baseUrl)
  if (url.origin !== baseUrl.origin || !url.pathname.startsWith(baseUrl.pathname)) {
    throw new TypeError('API path escaped configured base URL')
  }

  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== null && value !== undefined) {
      url.searchParams.set(key, String(value))
    }
  }
  return url
}

function composeAbort(caller: AbortSignal | undefined, timeoutMs: number) {
  const controller = new AbortController()
  let source: 'caller' | 'timeout' | null = null

  const onCaller = () => {
    if (source === null) source = 'caller'
    controller.abort(caller?.reason)
  }

  caller?.addEventListener('abort', onCaller, { once: true })
  if (caller?.aborted) onCaller()

  const timer = setTimeout(() => {
    if (source === null) source = 'timeout'
    controller.abort(new DOMException('Timed out', 'TimeoutError'))
  }, timeoutMs)

  return {
    signal: controller.signal,
    source: () => source,
    cleanup() {
      clearTimeout(timer)
      caller?.removeEventListener('abort', onCaller)
    },
  }
}

async function readUnknownBody(response: Response): Promise<unknown> {
  if (response.status === 204 || response.status === 205) return null

  const contentLength = Number(response.headers.get('content-length'))
  if (Number.isFinite(contentLength) && contentLength > MAX_JSON_CHARS) {
    throw new ApiFailure({
      kind: 'validation',
      issues: [{ path: '$', message: 'response exceeds size limit' }],
    })
  }

  const text = await response.text()
  if (text.length > MAX_JSON_CHARS) {
    throw new ApiFailure({
      kind: 'validation',
      issues: [{ path: '$', message: 'response exceeds size limit' }],
    })
  }
  if (text === '') return null

  const contentType = response.headers.get('content-type') ?? ''
  if (!contentType.includes('json')) return { nonJson: true }

  try {
    return JSON.parse(text) as unknown
  } catch {
    return { invalidJson: true }
  }
}
```

仅看 `Content-Length` 不够：它可能缺失、错误，或经过压缩后代表传输大小而非解压后内存。上例仍对读出的文本设上限，但真正超大响应应在网关限制或使用流式 parser，避免先整体占内存。

### 3. Problem decoder

```ts
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

const problemDecoder: Decoder<ProblemDetail> = {
  decode(input) {
    if (
      !isRecord(input) ||
      typeof input.title !== 'string' ||
      typeof input.status !== 'number' ||
      typeof input.code !== 'string'
    ) {
      return { ok: false, issues: [{ path: '$', message: 'invalid problem detail' }] }
    }

    return {
      ok: true,
      value: {
        title: input.title,
        status: input.status,
        code: input.code,
        detail: typeof input.detail === 'string' ? input.detail : undefined,
        requestId: typeof input.requestId === 'string' ? input.requestId : undefined,
        type: typeof input.type === 'string' ? input.type : undefined,
      },
    }
  },
}
```

### 4. Client 实现

```ts
export function createApiClient(config: {
  baseUrl: string
  fetchImpl?: typeof fetch
  defaultTimeoutMs?: number
}) {
  const baseUrl = new URL(config.baseUrl)
  if (!baseUrl.pathname.endsWith('/') || baseUrl.search || baseUrl.hash) {
    throw new TypeError('baseUrl must end with / and contain no query/hash')
  }
  const fetchImpl = config.fetchImpl ?? fetch
  const defaultTimeoutMs = config.defaultTimeoutMs ?? 15_000

  async function request<T>(path: string, options: RequestOptions<T>): Promise<T> {
    const url = makeUrl(baseUrl, path, options.query)
    const headers = new Headers(options.headers)
    headers.set('accept', 'application/json')
    if (options.idempotencyKey) headers.set('idempotency-key', options.idempotencyKey)

    let body: BodyInit | undefined
    if ('json' in options && options.json !== undefined) {
      headers.set('content-type', 'application/json')
      body = JSON.stringify(options.json)
    } else if ('form' in options && options.form !== undefined) {
      // 不设 content-type；浏览器生成 multipart boundary。
      body = options.form
    }

    const timeoutMs = options.timeoutMs ?? defaultTimeoutMs
    const abort = composeAbort(options.signal, timeoutMs)

    try {
      let response: Response
      try {
        response = await fetchImpl(url, {
          method: options.method ?? 'GET',
          headers,
          body,
          signal: abort.signal,
          credentials: options.credentials ?? 'include',
        })
      } catch (error) {
        if (abort.source() === 'timeout') {
          throw new ApiFailure({ kind: 'timeout', timeoutMs })
        }
        if (abort.source() === 'caller') {
          throw new ApiFailure({ kind: 'aborted', reason: options.signal?.reason })
        }
        throw new ApiFailure({ kind: 'network', cause: error })
      }

      let bodyValue: unknown
      try {
        bodyValue = await readUnknownBody(response)
      } catch (error) {
        if (error instanceof ApiFailure) throw error
        if (abort.source() === 'timeout') {
          throw new ApiFailure({ kind: 'timeout', timeoutMs })
        }
        if (abort.source() === 'caller') {
          throw new ApiFailure({ kind: 'aborted', reason: options.signal?.reason })
        }
        // 响应头已经到达，body stream 仍可能因连接中断而失败。
        throw new ApiFailure({ kind: 'network', cause: error })
      }
      const requestId = response.headers.get('x-request-id') ?? undefined

      if (!response.ok) {
        const problem = problemDecoder.decode(bodyValue)
        if (problem.ok) {
          throw new ApiFailure({
            kind: 'problem',
            problem: { ...problem.value, status: response.status, requestId },
          })
        }
        throw new ApiFailure({
          kind: 'http', status: response.status, requestId,
          body: safeErrorSample(bodyValue),
        })
      }

      const decoded = options.decoder.decode(bodyValue)
      if (!decoded.ok) {
        throw new ApiFailure({
          kind: 'validation',
          issues: decoded.issues,
          sample: safeErrorSample(bodyValue),
        })
      }
      return decoded.value
    } finally {
      abort.cleanup()
    }
  }

  return { request }
}
```

`safeErrorSample` 应只保留类型、字段名和截断后的非敏感结构，不复制正文/token/服务端栈。204 endpoint 可以传一个只接受 `null` 的 decoder；显式契约比 client 猜返回类型可靠。

### 5. Repository 与领域转换

```ts
interface TicketDto {
  id: string
  title: string
  status: 'OPEN' | 'CLOSED'
  updated_at: string
}

const ticketDtoDecoder: Decoder<TicketDto> = {
  decode(input) {
    if (
      !isRecord(input) ||
      typeof input.id !== 'string' ||
      typeof input.title !== 'string' ||
      (input.status !== 'OPEN' && input.status !== 'CLOSED') ||
      typeof input.updated_at !== 'string'
    ) return { ok: false, issues: [{ path: '$', message: 'invalid TicketDto' }] }

    return { ok: true, value: {
      id: input.id,
      title: input.title,
      status: input.status,
      updated_at: input.updated_at,
    } }
  },
}

function parseDate(value: string): Date {
  const date = new Date(value)
  if (Number.isNaN(date.valueOf())) {
    throw new ApiFailure({
      kind: 'validation',
      issues: [{ path: 'updated_at', message: 'invalid ISO timestamp' }],
    })
  }
  return date
}

class TicketRepository {
  constructor(private readonly api: ReturnType<typeof createApiClient>) {}

  async getById(id: TicketId, signal?: AbortSignal): Promise<Ticket> {
    const dto = await this.api.request<TicketDto>(
      `tickets/${encodeURIComponent(id)}`,
      { decoder: ticketDtoDecoder, signal },
    )
    return {
      id: ticketId(dto.id),
      title: dto.title,
      status: dto.status === 'OPEN' ? 'open' : 'closed',
      updatedAt: parseDate(dto.updated_at),
    }
  }
}
```

### 6. 必测场景

```ts
it('2xx 合法 JSON 经 decoder 返回')
it('2xx 缺字段抛 validation 而非返回伪 T')
it('204 交给 null decoder')
it('404 problem 保留 status/code/requestId')
it('500 HTML 归一为 http error')
it('caller abort 映射 aborted')
it('timeout 映射 timeout 并清 timer')
it('decoder 内部协议失败不映射为 network')
it('FormData 不设置 content-type')
it('绝对外部 URL 被拒绝')
it('DTO 日期非法在 repository 边界失败')
```

用 MSW 模拟 HTTP 协议，用注入 `fetchImpl` + fake timers 精测 abort/timeout。不要在每个组件 mock repository 内部实现；组件测试只关心 repository 的成功/失败契约。

### 7. 错误答案

- `return response.json() as T`：没有验证。
- `catch { throw new Error('请求失败') }`：丢掉 abort、timeout、status、request id。
- 超时后自动重放所有 POST：可能重复创建。
- 给 FormData 手设 `multipart/form-data`：丢 boundary，服务端解析失败。
- client 接受任意绝对 URL：可能把凭证带往不可信 origin（具体 credentials/CORS 仍会限制，但设计不应依赖偶然限制）。

---

## 题 2 参考答案：认证恢复与业务重放必须分开判断

### 1. 认证协调器

```ts
interface ReplayableRequest<T> {
  execute(options: { bypassAuthRecovery: boolean }): Promise<T>
  replayPolicy: 'safe' | 'idempotency-key' | 'never'
}

export function createAuthCoordinator(deps: {
  refreshBare(): Promise<void>
  clearSession(): void
  clearSensitiveCache(): void
  notifyExpiredOnce(): void
}) {
  let refreshInFlight: Promise<void> | null = null
  let authEpoch = 0
  let expiredNotifiedAtEpoch: number | null = null

  function refreshOnce(): Promise<void> {
    if (refreshInFlight) return refreshInFlight
    const startedEpoch = authEpoch

    const task = deps.refreshBare()
      .then(() => {
        if (startedEpoch !== authEpoch) {
          throw new ApiFailure({ kind: 'aborted', reason: 'auth epoch changed' })
        }
      })
      .catch((error) => {
        if (startedEpoch === authEpoch) expireSession()
        throw error
      })
    const wrapped = task.finally(() => {
      if (refreshInFlight === wrapped) refreshInFlight = null
    })
    refreshInFlight = wrapped
    return wrapped
  }

  function expireSession() {
    deps.clearSession()
    deps.clearSensitiveCache()
    if (expiredNotifiedAtEpoch !== authEpoch) {
      expiredNotifiedAtEpoch = authEpoch
      deps.notifyExpiredOnce()
    }
  }

  function logout() {
    authEpoch++
    // 不把仍在运行的 promise 从 singleflight 槽中提前移除；否则会并发启动第二次 refresh。
    // 旧任务完成后会因 epoch 不同而拒绝，并由 finally 安全清槽。
    expiredNotifiedAtEpoch = null
    deps.clearSession()
    deps.clearSensitiveCache()
  }

  async function recoverAndReplay<T>(request: ReplayableRequest<T>): Promise<T> {
    if (request.replayPolicy === 'never') {
      throw new ApiFailure({
        kind: 'http', status: 401,
        body: { message: 'request result unknown; manual reconciliation required' },
      })
    }

    await refreshOnce()
    // 调用方只允许进入此函数一次；execute 设置 bypass，第二个 401 直接失败。
    return request.execute({ bypassAuthRecovery: true })
  }

  return { refreshOnce, recoverAndReplay, logout }
}
```

`refreshBare` 使用不安装 401 恢复拦截器的裸 client。`replayPolicy='safe'` 适用于 GET；`idempotency-key` 只有服务端确认支持且原 key 保持不变时可重放；`never` 用于一次性 stream、结果未知的非幂等动作。

### 2. 20 并发测试

```ts
it('20 个调用共享一次 refresh', async () => {
  const gate = deferred<void>()
  const refreshBare = vi.fn(() => gate.promise)
  const auth = createAuthCoordinator({
    refreshBare,
    clearSession: vi.fn(),
    clearSensitiveCache: vi.fn(),
    notifyExpiredOnce: vi.fn(),
  })

  const retries = Array.from({ length: 20 }, () => auth.refreshOnce())
  expect(refreshBare).toHaveBeenCalledTimes(1)

  gate.resolve()
  await Promise.all(retries)
  expect(refreshBare).toHaveBeenCalledTimes(1)
})

it('refresh 期间 logout 后，旧 refresh 不能恢复会话', async () => {
  const gate = deferred<void>()
  const establish = vi.fn()
  const auth = createAuthCoordinator(testDeps({
    refreshBare: async () => { await gate.promise; establish() },
  }))

  const pending = auth.refreshOnce()
  auth.logout()
  gate.resolve()

  await expect(pending).rejects.toMatchObject({ detail: { kind: 'aborted' } })
  // 更理想的 refreshBare 只返回凭证结果，由 epoch 检查后再 establish，
  // 这样 establish 本身也不会发生；本测试提醒你不要在裸函数内直接写 session。
})

it('refresh 失败只清缓存和通知一次')
it('replay 后第二次 401 不再次 refresh')
it('never 请求不自动重放')
it('带同一个 idempotency key 的创建只产生一个服务端结果')
```

上例第二个测试暴露了一个重要设计改进：`refreshBare()` 最好返回 `SessionPayload`，协调器通过 epoch 后才 `establish(payload)`；不要让裸函数先写全局状态。生产实现应采用这一改进。

### 3. 富文本信任管线

```text
编辑器产生 HTML/结构化文档
  -> 服务端验证大小、schema、权限
  -> 存储原始格式（按产品策略）
  -> 展示前服务端或前端成熟 sanitizer
       allow tags: p, ul, li, strong, em, a, code ...
       allow attrs: href, title ...
       allow schemes: https, mailto（按需求）
       deny: style, on*, script, object, unsafe svg ...
  -> Trusted Types（支持时）/ v-html 单一封装点
  -> CSP 限制脚本、frame、connect 等
```

应用中只允许一个审查过的 `<SafeRichText>` 使用 `v-html`；业务组件不能直接用。若 sanitizer 失败，显示纯文本或错误态，绝不回退原 HTML。

恶意样本回归至少包括：事件属性、`javascript:` URL、编码 URL、SVG/onload、破损嵌套标签、超长属性、iframe 非白名单 origin、CSS URL。具体攻击语料使用所选 sanitizer 官方测试集并持续升级。

### 4. CSRF 与 CORS 分工

Cookie 自动随符合规则的请求携带，所以变更接口应：

- `Secure + HttpOnly + 合适 SameSite`；
- POST/PATCH/DELETE，不用 GET 改状态；
- 服务端验证 CSRF token；
- 服务端校验 Origin/Referer 作为纵深；
- CORS 只允许明确可信 origin 和必要 header/method。

CORS主要控制浏览器跨源读取/请求能力，不保证攻击者无法诱导浏览器发送简单请求；因此不能单独当 CSRF 防线。CSP主要限制页面加载/执行资源，不能替代内容清洗和服务端授权。

### 5. 分片上传状态机

```ts
type UploadState =
  | { status: 'queued'; file: File }
  | { status: 'initializing'; file: File }
  | { status: 'uploading'; uploadId: string; completed: ReadonlyMap<number, string>; sentBytes: number }
  | { status: 'paused'; uploadId: string; completed: ReadonlyMap<number, string> }
  | { status: 'verifying'; uploadId: string }
  | { status: 'success'; assetId: string }
  | { status: 'error'; uploadId?: string; retryable: boolean; error: unknown }
  | { status: 'canceled' }
```

协议：

```text
POST /uploads {name,size,declaredType,wholeChecksum?}
  <- uploadId, partSize, signed part URLs/URL factory, expiresAt

最多 4 个 worker:
  slice file -> 可选 hash -> PUT signed URL
  <- ETag/checksum
  checkpoint {uploadId, file fingerprint, completed parts}

POST /uploads/:id/complete {parts:[number,etag]}
  <- verifying / asset

GET /uploads/:id
  <- 超时后查询最终状态

DELETE /uploads/:id
  <- abort；失败则服务端 TTL 回收孤儿 part
```

客户端检查：明显的大小/type、网络状态、part checksum、UI 限流。服务端检查：登录和租户权限、配额、真实内容、总大小、part 完整性/checksum、uploadId 所有者、签名范围、病毒扫描/媒体重编码、文件名安全。对象存储密钥永不下发，只发短期最小权限 URL。

part PUT 应可按 `uploadId + partNumber` 幂等；指数退避只重试网络/5xx/429，遵守总预算。完成提交超时不创建新 upload，先 GET 状态。

### 6. 下载边界

1. `response.ok`；
2. 错误 content-type 先按 problem 解析；
3. 成功类型必须在 endpoint 白名单；
4. 文件名移除 `/\\`、控制字符和危险尾缀，设置默认值；
5. `URL.createObjectURL` 后 `finally revokeObjectURL`；
6. 大文件优先受控签名 URL/流，不一次性进内存。

### 7. 生产限制

- 前端 singleflight 只协调一个 tab；跨 tab 可通过 BroadcastChannel 通知 session 变化，但服务端仍要处理并发 refresh。
- Abort 上传不会自动删除已到对象存储的 part，必须有 abort/TTL。
- HttpOnly Cookie 降低 token 被 JS 直接窃取的概率，不会修复页面内 XSS 能代表用户发请求的问题。
- CSP 与第三方编辑器/上传 SDK 需要先 report-only 验证，不能上线即用宽泛 `*` 放行。
- 对象存储回调、扫描完成属于异步最终一致性，UI 需要 `verifying`，不能上传完就宣称可用。

### 8. 错误方案

- 20 个 401 各自 refresh：惊群与凭证轮换竞态。
- refresh 使用同一 interceptor：递归 401。
- logout 只清 UI：旧 refresh/请求回来重新写缓存。
- 正则删除 `<script>`：无法覆盖事件属性、URL、SVG 等解析上下文。
- 客户端 `accept="video/*"` 当安全验证：可绕过。
- 上传完成请求超时就重新上传 2GB：重复资源与费用。

### 复建要求

不看答案重新画两条时间线：

1. 20 个 401 汇聚到一次 refresh，再各自最多 replay 一次；
2. 2GB 文件从 initialize、part workers、complete、verify 到 abort/TTL。

然后在每个网络超时点写下：“服务端可能已经发生了什么，我用什么键查询/去重？”
