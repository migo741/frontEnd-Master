# 第 05 章练习

## 练习一：生产级 `useOnlineStatus`

基础需求：订阅 `window` 的 `online/offline`，返回 `{isOnline, changedAt}`。

高级约束：

- SSR 不访问 window，服务端快照可配置为 `unknown`，水合不报错。
- 多个组件使用时语义一致；挂载/卸载不泄漏监听器。
- 浏览器的 `navigator.onLine` 只代表网络接口状态，不代表业务 API 可用。增加可选 `probe(): Promise<boolean>` 与退避重试，返回 `online | offline | degraded | unknown`。
- 页面 hidden 时暂停主动 probe，visible 时立即校验。
- 请求取消、失败分类和最后成功时间有明确模型。

先完成原生在线状态的 `useSyncExternalStore` 版本，再把 probe 作为独立层组合，别造一个无法测试的巨型 Effect。

## 练习二：最小外部 Store（高难）

实现：

```ts
const store = createStore({count: 0, user: null as User | null})
store.getSnapshot()
store.setState(prev => ({...prev, count: prev.count + 1}))
store.subscribe(listener)

const count = useStore(store, s => s.count)
```

要求：

- 同值更新不通知；一次更新所有 listener 看到同一新快照。
- `getSnapshot` 在未更新时引用稳定。
- 取消订阅幂等；listener 在通知中取消自己不破坏本轮其他 listener。
- selector 只在选中值变化时让组件呈现新值；支持自定义 equality。
- 写 StrictMode 测试、两个切片隔离测试、SSR 初始快照测试。
- 写一段说明：该练习为何不能直接成为生产状态库。

提示：通知时遍历 listeners 的副本；selector 层可以缓存上一次 snapshot 和 selection，但要小心闭包与并发语义。可查官方的 `useSyncExternalStoreWithSelector` 实现思路，禁止直接复制。

