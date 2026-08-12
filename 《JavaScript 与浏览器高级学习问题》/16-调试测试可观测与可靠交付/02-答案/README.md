# 第 16 章参考答案

## 练习一

最小不变量：本地 draft 有单调 `revision`；响应只能确认自己发送的 revision，不能携带旧正文覆盖当前 state；切换文档会结束旧 session；409 是显式冲突状态，不自动假装成功。

状态可建模为：

```text
clean -> dirty -> saving(revision, requestId)
saving + newer edit -> dirty-with-inflight
saving + same revision success -> clean
saving + older success -> ignore acknowledgement
any + conflict -> conflicted(localVersion, serverVersion)
session changed -> abort old, ignore all old events
```

核心 reducer 只接受有身份的事件：

```js
function reduce(state, event) {
  switch (event.type) {
    case 'edited':
      return {...state, text: event.text, revision: state.revision + 1, status: 'dirty'}
    case 'saveStarted':
      if (event.sessionId !== state.sessionId) return state
      // debounce 若晚于更新或文档切换到达，不能把旧 revision 立为权威请求。
      if (event.revision !== state.revision) return state
      return {...state, active: {requestId: event.requestId, revision: event.revision}, status: 'saving'}
    case 'saveSucceeded': {
      if (event.sessionId !== state.sessionId) return state
      if (event.requestId !== state.active?.requestId) return state
      if (event.revision < state.revision) return {...state, active: null, status: 'dirty'}
      return {...state, active: null, savedRevision: event.revision, status: 'clean'}
    }
    case 'conflicted':
      if (event.sessionId !== state.sessionId) return state
      if (event.requestId !== state.active?.requestId) return state
      return {...state, active: null, status: 'conflicted', conflict: event.payload}
    case 'saveFailed':
      if (event.sessionId !== state.sessionId) return state
      if (event.requestId !== state.active?.requestId) return state
      return {...state, active: null, status: 'dirty', lastError: event.error}
    case 'sessionChanged':
      return {
        sessionId: event.sessionId,
        text: event.text,
        revision: 0,
        savedRevision: 0,
        active: null,
        status: 'clean',
        conflict: null,
        lastError: null,
      }
    default:
      return state
  }
}
```

transport 的 deferred 测试可精确反序：

```js
const a = deferred()
const b = deferred()
transport.save.mockReturnValueOnce(a.promise).mockReturnValueOnce(b.promise)

edit('old'); manualSave() // A
edit('new'); manualSave() // B
b.resolve({revision: 2})
a.resolve({revision: 1})
await flushMicrotasks()

expect(model.text).toBe('new')
expect(model.savedRevision).toBe(2)
```

身份检查必须先于 revision 分支。B 已成功后 `active` 为 null；此时 A 迟到必须原样忽略，不能因 `A.revision < state.revision` 把 clean 改回 dirty。上例选择“同一时刻只有一个权威 active 请求”；若产品允许多个 in-flight，则应以 `Map<requestId, revision>` 建模，不能继续复用单个 `active` 字段。

再测一个 debounce 反例：切换到 session B 后才派发 A 的 `saveStarted`，reducer 必须保持 B 的 `clean/dirty` 状态和 `active: null`；A 随后的 success/failure/conflict 也全部无效。控制器处理 `sessionChanged` 时还应先 abort A 的 transport 和 debounce timer，reducer 的身份守门是最后一道保险，不是取消操作的替代品。

服务端也应使用版本/ETag 或幂等键阻止最后到达的旧写覆盖新写；只在前端忽略旧响应不能防止服务器数据已经回滚。

遥测记录 document 的不可逆 hash/内部 id、sessionId、requestId、revision、结果类别、耗时和 release，不记录正文。AbortError 作为计数指标而非异常告警；网络失败按预算重试；409 进入产品可解决的冲突 UI；不变量破坏高优先上报。

## 练习二

前 30 分钟应先降低影响：暂停扩量，按能力关闭相关 flag；不要立即清空所有缓存或强推 SW，这可能扩大不可逆状态。同步冻结 release artifact、Source Map、响应头和 API schema 版本。

复现矩阵的最小维度：

| 维度 | A | B |
|---|---|---|
| 前端 | old | new |
| flag | off | on |
| SW/cache | clean | legacy upgraded |
| API | old schema | new schema |
| browser | Safari target | Chromium control |

用 pairwise 先缩小，再复现命中组合。Source Map 必须按错误事件的 release id 选择，而不是拿当前 main 分支映射。

建议新增的低噪声事件：启动阶段 checkpoint（HTML loaded、entry loaded、config parsed、root mounted）、chunk URL/状态、SW controller/version、API schema version、flag snapshot hash、错误 name/stack/cause、浏览器版本。响应只记录 schema 校验错误路径/期望类型，不上传值。

候选实验：

1. 新前端 + flag off 是否消失，验证功能分支；
2. 新前端 + 清洁 profile 是否消失，验证 SW/cache；
3. 固定旧/新 API fixture，验证字段兼容；
4. Safari 加载实际旧 chunk 与新 runtime 混合，验证缓存原子性；
5. 本地按正确 release Source Map 还原 `t` 的真实调用点。

常见真实链可能是旧 SW 缓存了非内容哈希入口，新 HTML/旧 chunk 混装，再由 flag 进入使用新 schema 的路径；但在证据出现前这只是候选，不应写成结论。

修复需让静态资源内容哈希且长期 immutable、HTML/no-cache、SW 更新有双版本兼容和激活策略、API 做向后兼容解析。灰度按 Safari+旧 SW cohort 观察启动成功率；回滚要保留新旧 API/schema 兼容期。

复写任务：把方案压缩成一页 incident timeline，每个动作写“要验证的假设”和“成功/失败后的下一步”。
