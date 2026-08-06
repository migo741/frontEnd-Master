# 第 04 章练习

## 练习一：不会被旧响应覆盖的搜索

实现用户搜索：输入 300ms 后请求 `/api/users?q=...`。模拟网络延迟，使旧查询可能晚于新查询返回。

要求：

- 空查询不发请求并回到 idle；状态用判别联合。
- 新查询开始时取消旧请求；旧响应即使仍完成也不得覆盖新结果。
- 区分 AbortError 与真实网络错误。
- 卸载后不更新状态；StrictMode 下不出现可见错误。
- 输入立即响应，loading/error/result 有可访问提示。
- 用假定时器 + 可控 Promise 写竞态测试：A 后返回、B 先返回，最终只展示 B。

完成基础版后写 150 字说明：为什么在真实应用中更推荐路由 loader/query 库？

## 练习二：主题变化不重连的聊天室（高难）

给定：

```ts
declare function createConnection(roomId: string): {
  connect(): void
  disconnect(): void
  on(event: 'connected' | 'message', fn: (...args: any[]) => void): void
  off(event: 'connected' | 'message', fn: (...args: any[]) => void): void
}
```

需求：

- `roomId` 改变必须断开旧房间并连接新房间。
- `theme` 改变不能重连，但下一条 toast 使用最新 theme。
- message handler 使用最新的 `mutedWords` 过滤；过滤词改变不能重连。
- StrictMode 下任意时刻最多一个活动连接；监听器不泄漏。
- 分别给出 React 19.2 `useEffectEvent` 方案和 React 18 兼容方案。

测试连接/断开次数、handler 引用对称、最新 theme/过滤词行为。

## 反思

从你过去写过的 Vue `watch/watchEffect` 或 React `useEffect` 中挑一个，判断它属于外部同步、派生数据还是事件动作，并给出重构。

