# 第 12 章参考答案

## 练习一

核心是把“领取”做成 IDB 的原子本地事实，把慢网络放到事务外。所有完成操作都携带 fencing token，旧执行者即使恢复也只能得到 no-op。

数据记录：

```js
{
  id,
  status: 'queued' | 'claimed',
  createdAt,
  nextAttemptAt,
  ownerId: null,
  leaseUntil: 0,
  token: 0,
  operation,
  payload,
}
```

在真实实现中建议建复合索引支持状态/时间查询。下面展示事务边界；`selectCandidates` 应在 IDB request 成功回调链中完成选择和 `put`，不要插入 timer/network await：

```js
export function claimBatch(db, {ownerId, now, leaseMs, limit}) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction('outbox', 'readwrite')
    const store = tx.objectStore('outbox')
    const claimed = []
    const request = store.index('byCreatedAt').openCursor()

    request.onerror = () => tx.abort()
    request.onsuccess = () => {
      const cursor = request.result
      if (!cursor || claimed.length >= limit) return
      const item = cursor.value
      const eligible = item.status === 'queued'
        ? item.nextAttemptAt <= now
        : item.status === 'claimed' && item.leaseUntil <= now

      if (eligible) {
        const next = {
          ...item,
          status: 'claimed',
          ownerId,
          leaseUntil: now + leaseMs,
          token: item.token + 1,
        }
        cursor.update(next)
        claimed.push(next)
      }
      cursor.continue()
    }

    tx.oncomplete = () => resolve(claimed)
    tx.onabort = tx.onerror = () => reject(tx.error ?? new Error('claim transaction aborted'))
  })
}
```

`openCursor` 到末尾后事务才能完成。两个重叠 `readwrite` 事务在该对象仓库上被序列化，因此第二个会看见第一个已写的 claim。复杂生产实现还要避免扫全表，使用 `status/nextAttemptAt/createdAt` 可查询索引并分别查询 queued/expired。

网络阶段：

```js
for (const item of claimed) {
  try {
    const result = await send(item, {idempotencyKey: item.id})
    await finalize(db, item, {type: 'confirmed', result})
  } catch (error) {
    await finalize(db, item, classify(error))
  }
}
```

`finalize` 新开 readwrite 事务，先读当前记录；仅当 `current.ownerId === item.ownerId && current.token === item.token` 才更新/删除。若租约过期后别人已领取，旧结果不能落库；服务端幂等键保证重复发送也不重复生效。

客户端时钟跳变说明 lease 只是并发优化。真正业务正确性仍由幂等键、实体 version 和服务端鉴权守住。崩溃留下 claimed，租约到期可重领；quota/abort 明确失败并上报，不能假装已保存。

## 练习二

推荐把一份实体拆成三类事实：

```text
base:    最近一次确认的服务端版本
local:   用户当前草稿/基于 base 的 patch
outbox:  已冻结、等待发送的 mutation(intent)
```

BroadcastChannel 只发送：

```js
{version: 1, type: 'entity.changed', entityId, serverVersion, senderId}
```

接收端若本地 clean，重读数据库/服务端；若 dirty，标记“远端有新版本”，不直接覆盖编辑区。消息重复或乱序通过 `serverVersion <= knownVersion` 忽略；晚加入标签页直接从 IDB/API 建立当前事实。

状态转移关键点：

```text
edit: clean -> dirty
persist locally: dirty -> queued
claim: queued -> sending
2xx(version N): sending -> confirmed -> clean(base=N)
409(remote): sending -> conflicted(base, local, remote)
timeout: sending -> unknown -> query mutation status
abort before send: sending -> queued
permanent validation failure: sending -> failed(user action required)
```

三方合并只自动接受“一侧相对 base 改动”的字段；双方都改同一字段时呈现明确选择。数组顺序、富文本和权限字段不应使用通用深合并。高风险操作在 unknown 时先查询，不直接重放。

八个关键测试：

1. A/B 同时领取，只有不同 token 的当前 owner 可确认；
2. 重复 BroadcastChannel 消息不重复应用；
3. 旧 version 通知不回滚；
4. A 暂停、租约过期，B 完成后 A 恢复不能 finalize；
5. 服务端提交但响应丢失，mutation 查询恢复 confirmed；
6. SW 发送中被终止，重启后租约/幂等恢复；
7. 409 产生冲突 UI，双方改同字段不静默覆盖；
8. 配额/数据库清理后 UI 明确告知未持久化并阻止虚假“已保存”。

账号切换必须按用户命名空间隔离数据库/记录，并在退出时停止 flush、清理敏感本地数据和广播 session-ended；旧会话的异步结果还要经过 session id 守门。

剩余风险应诚实记录：Background Sync 覆盖不统一、客户端时钟租约不可靠、浏览器可清理数据、复杂富文本合并需要专用算法。设计目标不是“永不冲突”，而是冲突可发现、可解释、不静默丢数据。

复写任务：关闭答案，只画 `queued -> claimed -> network -> finalize`，逐个标出崩溃点；每个崩溃点都必须说明重启后从哪个持久事实恢复。

