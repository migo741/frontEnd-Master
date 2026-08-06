# 第 07 章参考答案

## 练习一：关键设计

```ts
const usersKey = {
  root: ['users'] as const,
  lists: () => [...usersKey.root, 'list'] as const,
  list: (input: CanonicalFilters) => [...usersKey.lists(), input] as const,
  details: () => [...usersKey.root, 'detail'] as const,
  detail: (id: string) => [...usersKey.details(), id] as const,
}
```

先用 codec 生成固定字段顺序/默认值的 `CanonicalFilters`，不要直接把临时表单对象当 key。

示例策略（不是普适常数）：企业用户目录 30 秒内变化不敏感，可列表 `staleTime: 30_000`；详情编辑频繁可 10 秒；离开后 10 分钟回访较常见，`gcTime: 10 * 60_000`。401/403/404/422 不重试，网络/502/503 最多 2 次带抖动。真正数值应由产品一致性要求、流量和监控调整。

loader 与组件必须复用 options：

```ts
const userListOptions = (filters: CanonicalFilters) => queryOptions({
  queryKey: usersKey.list(filters),
  queryFn: ({signal}) => api.listUsers(filters, signal),
  staleTime: 30_000,
})

export async function loader({request}: LoaderArgs) {
  const filters = parseSearch(new URL(request.url))
  await queryClient.ensureQueryData(userListOptions(filters))
  return {filters}
}
```

编辑成功：`setQueryData(detail(id), serverUser)`；对 active 列表可以用结构共享替换该 id，随后 invalidate `lists()` 让不在内存/复杂排序过滤的列表最终一致。不要假定改名后仍符合当前搜索过滤。

## 练习二：两种合格策略

### 策略 A：同实体串行化（推荐先做）

保存用户最新意图 `desiredLiked`，同一 message 同时只发一个请求；请求完成后若权威状态与最新意图不同，再发下一次。UI 展示 latest intent。优点是服务器顺序清晰、回滚简单；缺点是多一次延迟，需合并快速点击。

### 策略 B：可组合 optimistic patches

不保存整个 previous snapshot。维护以 clientMutationId 标识的 pending intents：

```ts
type LikeBase = {liked: boolean; count: number; version: number}
type Intent = {id: string; desired: boolean; status: 'pending' | 'failed'}

function project(base: LikeBase, intents: Intent[]) {
  return intents.reduce((view, intent) => {
    if (intent.status === 'failed' || view.liked === intent.desired) return view
    return {...view, liked: intent.desired, count: view.count + (intent.desired ? 1 : -1)}
  }, base)
}
```

成功响应推进 base 并移除对应/已被服务器版本覆盖的 intent；失败只移除自己的 intent，然后从 base + 剩余 intents 重算。因此 A 失败不会恢复一个过时整对象并覆盖 B。最终 invalidate 获取权威状态。

服务端必须支持 idempotency key 和版本检查；409 后拉取新 base 并重放仍有效意图。离线可进入待同步队列，但点赞若不值得持久队列，应明确提示并回滚。401 不能重试风暴，应暂停、触发会话恢复。

