# 第 08 章参考答案

## 练习一：归属建议

| 数据 | 建议 | 理由 |
|---|---|---|
| page/sort/query | URL | 可分享、刷新/前进后退恢复，唯一真相 |
| orders/loading/error | Query/loader | 服务端权威，需缓存/取消/失效 |
| 编辑弹窗草稿 | form/local | 临时、靠近使用点；提交后失效订单 query |
| 当前用户 | session endpoint 的 query + 轻量 auth context | 用户资料远端权威；服务端仍鉴权 |
| HttpOnly session | 浏览器 cookie | JS 不应读取；随请求发送 |
| access token 镜像 | 通常删除 | 扩大 XSS 泄漏面；按认证架构专门设计 |
| 侧栏展开 | layout local/context；需要跨会话再小型持久 store | 纯客户端偏好、低频 |
| 三步报价草稿 | feature store/reducer | 跨页共享、客户端拥有、需恢复/版本迁移 |
| toast 队列 | 专用短生命周期 service/store | 命令式跨树；不作为业务成功的唯一反馈 |
| WebSocket 实例 | service/ref | 非序列化资源；生命周期由 provider/service 管 |
| hover id | 行/表格局部 state 或事件层 | 高频瞬态，进入全局会造成广播 |
| 离线 mutation | 专用持久队列 + service | 需要幂等、版本、重放、迁移和安全策略 |

迁移用 strangler：先写 selectors/facade 保持旧组件接口；逐类建立新所有者；双读对比但单写；监控差异；按 feature flag 切换；最后删除旧字段。不要长期双写两个真相。

## 练习二：模型骨架

```ts
type PendingMove = {
  operationId: string
  taskId: string
  fromColumnId: string
  toColumnId: string
  toIndex: number
  baseVersion: number
}

type BoardState = {
  tasks: EntityState<Task, string>
  columns: EntityState<Column, string>
  users: EntityState<User, string>
  pendingMoves: Record<string, PendingMove>
  undoStack: UndoEntry[]
  sync: {status: 'online' | 'offline' | 'syncing'; schemaVersion: 2}
}
```

实体 Task 存 `columnId/rank/version`，Column 不复制完整 task。拖拽：

1. `taskMoveRequested` 记录 operation/baseVersion、保存可逆 patch、乐观更新 task column/rank。
2. service 发带 idempotency key 的请求。
3. confirmed 若 operation 仍 pending，用服务端 task/version 合并并移除 pending。
4. rejected 只逆转该 operation 的 patch；若其后有同 task 操作，先重取 base 再重放剩余 operations，不能恢复整板快照。
5. remote patch 若 version 连续且 task 无 pending，直接应用；有 pending 时进入 reconcile 队列或基于服务端 base 重放本地意图。

selector factory 按 columnId：先选择该列 task ids/ranks，再映射实体；无关实体引用不变时应复用结果。真正优化前用 React Profiler 验证。

WebSocket service 在 store 外持有连接和重连计时，收到消息后 schema 校验并 dispatch `remoteTaskPatchReceived`；中间件监听 requested action 发网络。State 只保存纯数据，才能回放、持久化和 DevTools 检查。

