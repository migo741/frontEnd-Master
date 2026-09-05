# 第 07 章练习：导航事务与无闪屏权限

> 两题分别训练“导航与数据竞态”和“权限/页面生命周期”。不要只交路由配置；必须把取消、失败、恢复和安全边界写清楚。

## 题 1：实现抗乱序的工单路由数据加载器（机制题）

### 背景

路由 `/tenants/:tenantId/tickets/:ticketId` 复用同一个 `TicketDetailPage`。用户可能在 1 秒内连续点击 5 条工单。接口支持 `AbortSignal`，但请求被 abort 前服务端可能已经完成；某些 mock Promise 也不会真正中止。

### 契约

实现：

```ts
function useRouteResource<K, T>(options: {
  key: Readonly<Ref<K | null>>
  load: (key: K, signal: AbortSignal) => Promise<T>
}): {
  state: Readonly<Ref<ResourceState<T>>>
  reload(): Promise<void>
}
```

`ResourceState<T>` 必须是可穷尽判断的 discriminated union，至少含 `idle/loading/success/error`。同时完成该详情路由的参数解析与 typed navigation 示例。

要求：

1. key 改变时取消上一次请求；
2. 即使旧 Promise 无视 abort 并成功，也不能覆盖新 key 的结果；
3. 组件 scope 销毁时清理；
4. loading 时可以保留上一份数据，但模板必须知道它是 stale/previous；
5. abort 不展示错误，真实错误可重试；
6. 无效 tenant/ticket ID 不发请求，进入 404 或 invalid 状态；
7. `reload()` 不能与 watch 产生无法解释的并发提交。

### 规模与限制

- 导航峰值 5 次/秒；
- 请求 p95 1.2 秒；
- 不允许通过给 `<RouterView :key="route.fullPath">` 强制销毁整个页面逃避问题；
- strict TypeScript，不用 `as` 伪造已验证 ID；
- 可用 Vitest fake/deferred Promise 测试。

### 失败语义

| 场景 | 期望 |
|---|---|
| A 慢、B 快 | 最终只显示 B |
| A 被 abort 后仍 resolve | A 结果被忽略 |
| B 网络失败 | 保留明确的 B 错误状态；不得回显为 A 成功 |
| key 变 null | 进入 idle，并阻止旧请求提交 |
| scope dispose | 取消资源，之后不提交状态 |

### 验收

- [ ] Abort 和 generation/sequence 两道门都存在；
- [ ] 测试可以控制 A/B resolve 顺序；
- [ ] 模板对四种状态做穷尽展示；
- [ ] route params 的运行时解析独立可测；
- [ ] 至少覆盖乱序、abort、error、dispose 四类测试；
- [ ] 解释何时应改用导航前 `beforeResolve + ensureQueryData`。

### 发散

- 如果 A、B 属于不同租户，除了 UI 竞态，还多了什么安全风险？
- 如果同一资源已有新鲜 query cache，loader 应怎样跳过网络？

---

## 题 2：设计一个无闪屏、多租户 RBAC 导航系统（生产开放题）

### 背景

OpsBoard 有公开登录页、需登录的普通页、需 `ticket:admin` 的管理页。刷新深链时会话未知；`/me` 耗时 0~1.5 秒。用户可以切租户，有未保存草稿；登录成功后支持返回原地址。应用会埋点、懒加载 chunk，并缓存列表页实例。

### 契约

提交：

1. 类型化的 `RouteMeta` 和路由记录；
2. `beforeEach`、`beforeResolve`、`afterEach` 的职责与核心代码；
3. `/me` singleflight 恢复状态机：`unknown/authenticated/anonymous`；
4. 安全的登录 redirect 解析，禁止开放重定向；
5. 切租户、权限不足、会话过期、实体 404 的跳转决策表；
6. 离开脏表单的 guard；
7. `scrollBehavior` 与有界 KeepAlive 策略；
8. 导航失败、chunk 加载失败的可观测与恢复策略；
9. 明确说明后端必须执行的授权。

### 规模与限制

- 60 条静态路由、8 个业务模块；
- 首屏不得渲染受保护页面后再跳走；
- 同时触发的 4 次导航只能请求一次 `/me`；
- KeepAlive 最多 6 个实例；
- chunk 失败最多自动刷新一次；
- 埋点不能上报 query 中的搜索词、redirect 或个人 ID；
- 不要求动态 `addRoute`，如使用必须说明幂等、深链恢复和 logout 清理。

### 失败语义

- `/me` 401：进入 anonymous，并安全重定向登录；
- `/me` 网络错误：显示可重试的 session-error，不把它当未登录；
- 权限不足：去 403，不发管理数据请求；
- 导航被新导航取代：不记成功 PV；
- 保存草稿失败：保持当前页面，不静默放行；
- 登录 redirect 非内部路径：回退 `/`。

### 验收

- [ ] 守卫不会产生重定向循环；
- [ ] 前端权限与后端安全边界明确分开；
- [ ] `afterEach` 检查 failure；
- [ ] `redirect` 经过内部路径白名单；
- [ ] 数据加载策略区分 critical 与 secondary；
- [ ] KeepAlive key/max/activated 生命周期有解释；
- [ ] 至少写 6 个端到端场景；
- [ ] 能画出一次成功导航和一次被取消导航的时序。

### 发散

- 权限在用户停留页面期间被服务端撤销，系统如何响应？
- 多 Tab 中一处 logout，其他 Tab 的导航与缓存应如何收敛？
