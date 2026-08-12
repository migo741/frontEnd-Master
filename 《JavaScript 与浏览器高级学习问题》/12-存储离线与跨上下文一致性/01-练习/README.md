# 第 12 章练习

## 练习一：原子领取离线任务

多个标签页和 Service Worker 共享 IndexedDB `outbox`。实现 `claimBatch(db, {ownerId, now, leaseMs, limit})`：

- 在一个短 `readwrite` 事务中选出 `queued` 或租约已过期的任务；
- 按 `createdAt` 排序，最多领取 `limit` 条；
- 每条写入新的 `ownerId`、`leaseUntil`、递增 fencing token 和 `claimed` 状态；
- 两个并发调用不能同时成功领取同一 `(id, token)`；
- 网络发送必须发生在事务提交后；
- 确认/失败使用新事务，并同时校验 owner + token，旧执行者不得覆盖；
- 处理 transaction abort、quota、页面崩溃和租约恢复；
- fake IndexedDB 或真实多页面测试并发领取、过期再领、旧确认和关闭连接。

交付一张两阶段时间线：`claim transaction -> network -> finalize transaction`，并解释为什么 `await fetch()` 不能放在 claim transaction 内。

## 练习二：多标签页离线编辑协议（高难）

为工单编辑器设计完整本地协议。标签页 A/B 可能编辑同一实体，网络可断开，Service Worker 可后台 flush，服务端使用 `version` 和 mutation 幂等键。

要求：

- IndexedDB 存 `base/local/outbox`，BroadcastChannel 只发版本通知；
- 自动保存状态至少有 `clean/dirty/queued/sending/confirmed/conflicted/unknown`；
- 同一实体操作有明确合并或顺序规则，队列有容量/TTL；
- 409 时做 base/local/remote 三方差异，不能静默 last-write-wins；
- timeout 后查询 mutation 结果，不能盲目重复高风险动作；
- upgrade blocked、配额不足、退出登录/换账号、数据库被清理都有 UX；
- 注入：重复消息、乱序通知、标签页暂停后恢复、SW 中途终止、服务端已提交但响应丢失；
- 指标：outbox 长度/最老年龄、重复、冲突、unknown、配额、迁移失败。

不要求实现 CRDT。提交状态图、数据 schema、关键伪码、至少八个协议测试和一份剩余风险说明。

