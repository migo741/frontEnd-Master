# 答案与复盘

## 题 1

参考归属：当前用户/租户/权限是 session store，刷新后由 `/me` 重建；分页和筛选是 URL，支持分享和前进后退；列宽是本地偏好并带 schema version；hover 是行组件本地；列表/详情是 query cache；草稿是 feature store 或页面状态，并显式提示离开；toast 是短生命周期 UI service；socket 是 app-level service，Pinia 只接收规范化后的领域事件，不持有原始连接对象。

关键不是唯一答案，而是每项能回答“谁销毁、谁更新、谁恢复”。把 socket 放进 reactive store 会带来序列化、代理和重连职责混乱。

## 题 2

```ts
const ticketKeys = {
  all: ['tickets'] as const,
  lists: () => [...ticketKeys.all, 'list'] as const,
  list: (q: TicketQuery) => [...ticketKeys.lists(), canonicalize(q)] as const,
  detail: (id: string) => [...ticketKeys.all, 'detail', id] as const,
}
```

参数 canonicalize 必须稳定排序并去掉 undefined。详情编辑成功后，直接更新 detail cache；对“确定包含该工单且排序位置不变”的列表可精准 patch，否则标记相关 list stale，在可见/聚焦时刷新。WebSocket 事件带 entity version：版本更高才应用；只收到 invalidation 时标脏，不猜完整实体。

乐观更新流程：`onMutate` 取消相关在途查询，快照旧缓存，应用 patch；失败恢复快照并呈现错误；settled 后按服务端真相 revalidate。若操作不可幂等、冲突代价高或服务端校验复杂，宁可 pessimistic update。高级不等于所有 mutation 都乐观。

