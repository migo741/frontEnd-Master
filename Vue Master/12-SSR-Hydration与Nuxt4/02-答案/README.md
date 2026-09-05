# 第 12 章答案：隔离、一致性、传输与缓存

## 题 1 参考答案：修复手写 SSR

### 1. 事故因果链

```text
模块加载一次
  → app/router/reactive state 成为进程 singleton
  → request A 写入 tenant A
  → await 期间 request B 写入 tenant B
  → A render 读取 B → HTML/payload 泄漏

server: Date.now + server timezone + random id S
client: 新时间 + browser timezone + random id C + 新 profile
  → 首次 vnode 不同 + 数据请求重复
  → mismatch / 节点修复 / 闪烁

个性化 HTML + public CDN cache
  → cache key 不含身份且响应可共享
  → 下一用户直接命中上一用户页面
```

这里最严重的是数据泄漏，先关闭共享缓存和 SSR 个性化响应，再处理体验问题。忽略 warning 不会修复任一安全根因。

### 2. 每请求 app factory

```ts
// app.ts
import { createSSRApp, reactive, type App, type InjectionKey } from 'vue'
import {
  createMemoryHistory,
  createRouter,
  createWebHistory,
  type Router,
} from 'vue-router'
import Root from './Root.vue'
import { routes } from './routes'

export interface PublicSession {
  readonly userId: string
  readonly tenantId: string
  readonly displayName: string
  readonly locale: string
  readonly timeZone: string
  readonly requestSeed: string
  readonly renderedAtIso: string
}

export const sessionKey: InjectionKey<PublicSession> = Symbol('public-session')

export function createApp(
  initial: PublicSession,
  target: 'server' | 'client',
): { app: App<Element>; router: Router } {
  const app = createSSRApp(Root)
  const router = createRouter({
    history:
      target === 'server'
        ? createMemoryHistory()
        : createWebHistory(),
    routes,
  })
  app.provide(sessionKey, reactive({ ...initial }))
  app.use(router)
  return { app, router }
}
```

服务端只返回公开状态：

```ts
// entry-server.ts
import { renderToString } from '@vue/server-renderer'
import { createApp, type PublicSession } from './app'

export interface RenderedPage {
  html: string
  publicState: PublicSession
  status: number
}

export async function renderPage(
  url: string,
  publicState: PublicSession,
): Promise<RenderedPage> {
  const { app, router } = createApp(publicState, 'server')
  await router.push(url)
  await router.isReady()
  const matched = router.currentRoute.value.matched.length > 0
  return {
    html: await renderToString(app),
    publicState,
    status: matched ? 200 : 404,
  }
}
```

客户端从框架/安全序列化通道得到状态，不自行重新请求：

```ts
// entry-client.ts
import { createApp, type PublicSession } from './app'

declare global {
  interface Window {
    __PUBLIC_STATE__: PublicSession
  }
}

const { app, router } = createApp(window.__PUBLIC_STATE__, 'client')
await router.isReady()
app.mount('#app')
```

`window.__PUBLIC_STATE__` 仅代表接口；真正 HTML shell 必须使用 SSR 工具链提供的安全 serializer，它要正确处理 `<`, `</script>`, Unicode 分隔符等。不能把 `JSON.stringify` 结果直接拼进 script。

### 3. 确定性协议

- `requestSeed` 在服务端一次生成，进入公开 state；组件用 seed + 字段路径派生稳定 id，或使用框架 SSR-safe id 能力。
- `renderedAtIso` 一次生成；两端首次显示同一 ISO/同一 locale+timezone 的结果。
- 用户时区已在 cookie/账户偏好中则写入 `timeZone`；未知时先稳定显示 UTC 或固定尺寸占位，mounted 后再显示本地值。
- 数据排序必须有稳定 tie-breaker，如 `createdAt DESC, id ASC`。
- payload 可放 displayName、允许用户看到的订单 DTO、locale/timezone；不可放 access token、HttpOnly cookie、服务凭证、内部 risk score、其他租户数据。

### 4. 缓存边界

| 对象 | 策略 |
| --- | --- |
| 带 hash JS/CSS | `public, max-age=31536000, immutable` |
| 公共 HTML | 可按 URL/locale/实验版本缓存，显式失效 |
| 登录 HTML/payload | `private, no-store`；不进共享 CDN |
| profile API | `private, no-store` 或严格用户私有缓存 |
| 公共商品 API | key 含 slug/locale/currency，短 TTL + tag 失效 |

若必须在 CDN 上运行个性化逻辑，仍不能缓存最终个性化 HTML 为公共对象；需要经安全审计的 edge compute、身份绑定 key、禁止缓存响应以及泄漏测试。

### 5. 测试与发布

1. 用 barrier 让 A/B 请求异步阶段交错，断言 A HTML/payload 只含 A，B 只含 B。
2. 服务端 HTML 放入真实浏览器 hydrate，监听 console，断言零 mismatch 和关键 DOM 未被替换。
3. 记录网络，首次 load 的 profile/订单只执行服务端一次并由 payload 复用。
4. 未匹配 URL 返回真实 404；redirect 和 auth status/header 真实可见。
5. displayName 设置为 `</script><script>...</script>`，断言不能闭合 payload script，也不会执行。
6. 两个不同 tenant 的 CDN 集成测试互不命中；登录响应为 private/no-store。
7. JS 加载失败时，HTML 仍不包含 secret 且关键内容可读。

最小止血：关闭个性化页面 public cache、滚回上一个安全版本或临时把敏感区域 CSR 且服务端重新鉴权、重启清空污染进程；长期才是 request factory、安全 payload 和端到端测试。回滚信号包括任何串租户、mismatch 上升、重复请求、错误率/TTFB 明显恶化。

### 6. 时区发散题

优先在登录 cookie 保存 IANA timezone，使两端相同。若首次匿名请求未知：首屏用明确标注的 UTC 文本并保持布局，mounted 后切换且告知时区；或者输出固定尺寸 skeleton。不要用服务端机房时区伪装用户时区。选择由“时间是否关键内容、SEO 是否需要、切换是否会误导”决定。

## 题 2 参考答案：Nuxt 4 混合渲染

### 1. 决策矩阵

| 路由 | 建议 | 原因与边界 |
| --- | --- | --- |
| `/`, `/pricing` | prerender，内容发布时重建 | 更新低频、SEO 高价值；紧急价格变更需失效/重建通道 |
| `/docs/**` | SSR + SWR/按 tag 失效，热点可 prerender | 10k 页全量构建成本高，分钟级更新 |
| `/catalog/:slug` | SSR/SWR 商品壳与价格；库存独立短轮询/stream | 价格和库存新鲜度不同，不能共用一个全页 TTL |
| `/dashboard/**` | universal SSR 或 CSR，`private, no-store` | 依据弱机首屏和服务器成本；绝不公共缓存个性化 HTML |
| `/editor/**` | client-only 重型编辑器 + SSR fallback | Canvas 依赖浏览器；fallback 提供标题、权限错误与加载失败路径 |
| report API | Node/Nitro 默认 | 服务 SDK/连接若不兼容 edge 就留 Node；只有依赖与数据源都适合才迁 edge |

概念配置：

```ts
export default defineNuxtConfig({
  routeRules: {
    '/': { prerender: true },
    '/pricing': { prerender: true },
    '/docs/**': { swr: 60 },
    '/catalog/**': { swr: 30 },
    '/dashboard/**': {
      ssr: true,
      headers: { 'cache-control': 'private, no-store' },
    },
    '/editor/**': { ssr: false },
  },
})
```

route rule 的精确能力以当前 adapter 文档为准。库存 API 返回 `private/no-store` 或极短缓存，并可按商品/仓库身份刷新；不能从缓存 30 秒的 HTML 推断实时库存。

### 2. 商品数据

```vue
<script setup lang="ts">
interface Product {
  slug: string
  title: string
  priceCents: number
  currency: string
}
interface Inventory { available: boolean; quantityBand: 'none' | 'low' | 'many' }

const route = useRoute()
const slug = computed(() => String(route.params.slug))

const { data: product, error } = await useAsyncData(
  () => `product:${slug.value}`,
  () => $fetch<Product>(`/api/catalog/${encodeURIComponent(slug.value)}`),
  { watch: [slug] },
)

if (error.value) throw createError({ statusCode: 404, statusMessage: 'Not found' })

const { data: inventory, refresh: refreshInventory } = useFetch<Inventory>(
  () => `/api/inventory/${encodeURIComponent(slug.value)}`,
  { key: () => `inventory:${slug.value}`, server: false },
)

let inventoryTimer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  inventoryTimer = setInterval(() => void refreshInventory(), 10_000)
})
onBeforeUnmount(() => {
  if (inventoryTimer !== undefined) clearInterval(inventoryTimer)
})
</script>
```

价格由 SSR payload 接管；库存客户端独立刷新。真实系统还需 tab hidden 暂停、退避、请求取消和“最后更新时间”。若库存对购买正确性关键，最终仍由下单接口原子校验。

### 3. 租户状态

```ts
interface PublicTenant { id: string; displayName: string }

export function useTenant() {
  return useState<PublicTenant | null>('current-tenant', () => null)
}
```

Nuxt 为请求上下文初始化并把它安全传给客户端；不能用模块顶层 `ref`。它仍对浏览器可见，所以只放 public DTO。授权每次在 server route 根据可信 session 重算，不能信客户端的 tenant id。

### 4. Nitro report route

```ts
interface ReportQuery { tenantId: string; from: string; to: string }
interface InternalReport { rows: unknown[]; debugSql: string }

export default defineEventHandler(async (event) => {
  const user = await requireUser(event)
  const raw = getQuery(event)
  const query = parseReportQuery(raw) as ReportQuery // 生产中由 schema 返回强类型
  await assertTenantMembership(user.id, query.tenantId)

  const aborter = new AbortController()
  const timeout = setTimeout(() => aborter.abort(), 8_000)
  try {
    const config = useRuntimeConfig(event)
    const upstream = await $fetch<InternalReport>(config.reportBaseUrl, {
      signal: aborter.signal,
      headers: { authorization: `Bearer ${config.reportServiceToken}` },
      query,
    })
    setHeader(event, 'cache-control', 'private, no-store')
    return { rows: validateAndMapRows(upstream.rows) }
  } catch (error: unknown) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw createError({ statusCode: 504, statusMessage: 'Report timed out' })
    }
    throw createError({ statusCode: 502, statusMessage: 'Report unavailable' })
  } finally {
    clearTimeout(timeout)
  }
})
```

`parseReportQuery` 必须校验日期格式、范围和最大窗口；错误日志带 request/trace id 但不记录 token。服务 token 只在 private runtime config，绝不能放 `runtimeConfig.public`。

### 5. 测试与观测矩阵

- SEO：无 JS 请求有 title、canonical、正文，404 为 404；结构化数据与页面 DTO 同源。
- Hydration：商品 SSR 后 hydrate 零 warning；locale/feature flag 一致。
- 缓存：并发 tenant A/B 不串；价格按 slug/currency；库存不命中过期页面 cache。
- 网络：商品首次不重复取数；库存按策略刷新且离开停止。
- Editor：服务端 fallback 可读；chunk 失败有 retry/error；未授权不下载敏感数据。
- Nitro：匿名 401、跨 tenant 404/403、坏输入 400、超时 504、上游错误 502、DTO 无内部字段。
- Edge：构建/集成测 Web API、包体、CPU、连接；不兼容时以相同 route 契约部署 Node。
- 观测：route、render mode、cache hit、server timing、release、tenant 匿名维度和 trace id；不采集 secret/完整 URL 查询。

### 6. CDN 秒开 dashboard 的决策

首选缓存公共静态 shell/assets，个性化 HTML/API 保持 private；必要时对不敏感、身份无关片段使用明确公共缓存。边缘个性化只有在能证明认证、cache key、禁止存储、日志隐私、数据地域、密钥与撤销策略，并有跨用户 fuzz/integration test 后才考虑。它同时增加平台锁定和事故半径，不能用“更快”跳过安全证明。

## 复写检查

合上答案后应能独立写出：

1. 每请求 app/router/store factory；
2. 一条安全、确定的 SSR payload 接管路径；
3. Nuxt 路由渲染与缓存矩阵；
4. `useAsyncData/useFetch/useState` 的正确身份 key；
5. 带鉴权、授权、schema、timeout、DTO 的 Nitro route；
6. 并发隔离、hydration、状态码和缓存泄漏测试。
