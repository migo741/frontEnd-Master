# 第 06 章参考答案

## 练习一：URL codec

```ts
const sorts = ['relevance', 'price-asc', 'price-desc'] as const
type Sort = typeof sorts[number]

type ProductSearch = {
  q: string
  category: string | null
  sort: Sort
  page: number
}

export function parseSearch(url: URL): ProductSearch {
  const p = url.searchParams
  const rawPage = Number(p.get('page'))
  return {
    q: (p.get('q') ?? '').trim().slice(0, 100),
    category: p.get('category')?.trim() || null,
    sort: sorts.includes(p.get('sort') as Sort) ? p.get('sort') as Sort : 'relevance',
    page: Number.isSafeInteger(rawPage) && rawPage >= 1 && rawPage <= 10_000 ? rawPage : 1,
  }
}

export function toSearchParams(value: ProductSearch) {
  const p = new URLSearchParams()
  if (value.q) p.set('q', value.q)
  if (value.category) p.set('category', value.category)
  if (value.sort !== 'relevance') p.set('sort', value.sort)
  if (value.page !== 1) p.set('page', String(value.page))
  return p
}
```

所有筛选变化都应把 page 重置为 1。loader：

```ts
export async function loader({request}: LoaderFunctionArgs) {
  const params = parseSearch(new URL(request.url))
  const response = await fetch(buildApiUrl(params), {signal: request.signal})
  if (response.status === 404) throw new Response('Not found', {status: 404})
  if (!response.ok) throw new Response('Upstream failed', {status: 502})
  return {params, products: await response.json()}
}
```

输入框可以保留局部 draft，因为“用户尚未提交的字符”不是 URL 真相；提交/debounce 后写 URL。replace 避免每个字符创建历史项，分页和明确筛选操作 push 便于后退。

预取只在链接 hover/focus 或接近 viewport、网络允许且缓存未命中时进行；全量预取浪费移动流量、挤占当前关键请求并可能压垮 API。

## 练习二：安全回跳

```ts
export function safeReturnTo(raw: string | null, fallback = '/') {
  if (!raw) return fallback
  try {
    const base = new URL('https://app.example.invalid')
    const target = new URL(raw, base)
    if (target.origin !== base.origin) return fallback
    if (!target.pathname.startsWith('/')) return fallback
    return `${target.pathname}${target.search}${target.hash}`
  } catch {
    return fallback
  }
}
```

使用标准 URL 解析并检查 origin，避免只判断 `startsWith('/')` 时放过 `//evil.com`。高安全场景还应 allowlist pathname，服务端校验并限制长度/编码。

边界建议：

- 根：会话/应用壳灾难，提供重新登录和全局追踪 id。
- `/org/:orgId`：组织不存在/无成员权限，仍保留根壳。
- report：404 就地显示“报表不存在”；5xx 提供局部重试，不摧毁组织导航。

服务端 API 对每次 billing 请求重新验证 owner；客户端 guard 只能减少无权限用户看到入口，无法阻止直接请求或篡改 JS。

chunk 404：捕获特定 chunk load error，记录 release/from/to/network，使用 sessionStorage 标记只自动刷新一次；CDN 资源使用 content hash 并保留上一版本，才是根治。无限刷新会造成事故放大。

