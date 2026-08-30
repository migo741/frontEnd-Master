# 答案与复盘

## 题 1

认证初始化需要 single-flight Promise，而不是一个易竞态 boolean：

```ts
let initPromise: Promise<void> | undefined
function ensureSession() {
  return initPromise ??= session.load().then(() => {
    addAllowedRoutes(session.permissions)
  }).catch(error => {
    initPromise = undefined
    throw error
  })
}

router.beforeEach(async to => {
  if (to.meta.public) return true
  if (!tokenStore.hasToken) return { name: 'login', query: { redirect: to.fullPath } }
  await ensureSession()
  if (!router.resolve(to.fullPath).matched.length) return to.fullPath
  if (!hasAll(to.meta.permissions)) return { name: 'forbidden' }
})
```

真实实现需避免无限 redirect：只在本次确实新增路由后 replace 原地址；404 catch-all 最后注册，或在动态注入后再判断。登出记录 removeRoute callbacks，清 session、重置 initPromise。测试覆盖首次深链、并发导航只调用一次 /me、无权限、登出再登录不同角色。

## 题 2

导航后加载：组件 watch `() => route.params.id`，每轮创建 AbortController，用 cleanup 取消，并用 version 防迟到；页面立即切到 2 的 skeleton，错误属于页面 2。导航前加载：在 `beforeResolve` 或稳定的数据加载层启动请求，导航取消时 abort；成功才提交路由，当前页面 1 在等待期间可显示全局进度。

前者感知更快，需处理空态；后者状态原子，但慢接口会“卡导航”。不要在 guard 中把数据写入全局 store 后又让页面发一次请求，应共享 cache/loader 结果并定义所有权。

