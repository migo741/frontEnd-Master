# 第 10 章参考答案

## 练习一：分层优化

```tsx
function SearchPage({records}: {records: RecordItem[]}) {
  const [query, setQuery] = useState('')
  const deferredQuery = useDeferredValue(query)
  const stale = query !== deferredQuery

  return (
    <>
      <label>搜索 <input value={query} onChange={e => setQuery(e.target.value)} /></label>
      <div aria-live="polite">{stale ? '结果更新中' : '结果已更新'}</div>
      <Results records={records} query={deferredQuery} stale={stale} />
    </>
  )
}
```

`useMemo(() => rank(records, query), [records, query])` 只避免相同依赖下的重复计算，首次/每个新 query 仍需计算。先把 normalize/token 索引在数据变化时构建，查询只做低成本 lookup；更重工作移 Web Worker并用 query id 丢弃旧结果。显示只虚拟化可视窗口，降低 DOM/布局成本。

Transition 只能在 React 的工作单元间让出；进入一个用户同步函数的 500ms 循环后，JS 主线程没有合作式 yield 点。应拆分/worker/改算法。

性能答案必须来自 profile：若瓶颈在布局/绘制，memo 组件无效；若在网络，Deferred Value 也不会减少请求，需要 debounce/cancel/cache。

## 练习二：推荐边界

```text
SessionBoundary + AppShell
├── Header（不 Suspense 或有独立小资源）
└── AccountRouteBoundary
    ├── AccountSummary Suspense/Error
    ├── Transactions Suspense/Error
    ├── Recommendations Suspense + 局部 Error/Retry
    └── Chat Suspense + 可关闭 Error Boundary
```

账户 401 交给 session boundary，清理敏感缓存并安全回登录；推荐 5xx 只影响推荐；聊天连接失败保留主业务。loader/server 在路由确定 accountId 后同时启动 summary/transactions/recommendations，Query cache 或 `Promise.allSettled` 配合独立边界。

切账户时旧内容可以显示为 dimmed，但所有 mutation 控件禁用或显式绑定旧 accountId，不能让用户以为在新账户操作。目标数据 ready 后原子切换。

Activity 可把已预取的详情子树设 hidden，保留返回状态并停用 effects；只对高概率导航且内存/数据敏感性允许时使用。React 18 用意图预取 query + route chunk，真正导航时挂载；需保留的表单状态提升到路由 store。

