# 第 03 章参考答案

## 练习一

分层解析：

```ts
type DecodeResult =
  | {ok: true; event: Event}
  | {ok: false; kind: 'invalid'; path: string; message: string}
  | {ok: false; kind: 'unknown-event'; type: string}

function decodeEvent(raw: unknown): DecodeResult {
  if (!isRecord(raw)) return {ok: false, kind: 'invalid', path: '$', message: 'expected object'}
  if (typeof raw.type !== 'string') {
    return {ok: false, kind: 'invalid', path: '$.type', message: 'expected string'}
  }
  if (!isRecord(raw.payload)) {
    return {ok: false, kind: 'invalid', path: '$.payload', message: 'expected object'}
  }

  switch (raw.type) {
    case 'ticket.created':
      if (typeof raw.payload.id !== 'string') return invalid('$.payload.id', 'expected string')
      if (typeof raw.payload.title !== 'string') return invalid('$.payload.title', 'expected string')
      return {ok: true, event: {type: raw.type, payload: {id: raw.payload.id, title: raw.payload.title}}}
    case 'ticket.assigned':
      if (typeof raw.payload.id !== 'string') return invalid('$.payload.id', 'expected string')
      if (typeof raw.payload.assigneeId !== 'string') return invalid('$.payload.assigneeId', 'expected string')
      return {ok: true, event: {type: raw.type, payload: {id: raw.payload.id, assigneeId: raw.payload.assigneeId}}}
    case 'heartbeat':
      if (typeof raw.payload.sequence !== 'number' || !Number.isSafeInteger(raw.payload.sequence)) {
        return invalid('$.payload.sequence', 'expected safe integer')
      }
      return {ok: true, event: {type: raw.type, payload: {sequence: raw.payload.sequence}}}
    default:
      return {ok: false, kind: 'unknown-event', type: raw.type}
  }
}
```

构造一个新对象也完成运行时投影，避免原 payload 夹带敏感字段。未知事件记录受限元数据并忽略/请求升级，不能把它当坏 payload 让连接无限重试。

## 练习二

核心返回：

```ts
type Result<T, E> = {ok: true; value: T} | {ok: false; error: E}
type TransitionError = {kind: 'not-allowed'; state: State['status']; action: Action['type']}

function transition(state: State, action: Action): Result<State, TransitionError> {
  switch (state.status) {
    case 'editing': return transitionEditing(state, action)
    case 'submitting': return transitionSubmitting(state, action)
    case 'completed': return transitionCompleted(state, action)
    default: return assertNever(state)
  }
}
```

每个子函数仍对所有 Action 做 switch，并在明确不允许集合中返回错误；default 用 assertNever，新增 Action 会报错。handler map 容易把 action payload 与 key 关联丢失，需要高级 mapped discriminated union 才安全，且错误常更差；状态数量中等时按 state 的 switch 最清晰。测试矩阵可显式列 `satisfies readonly Case[]`，但静态“覆盖所有笛卡尔组合”往往复杂过度，运行时生成组合 + 每个实现的 `never` 已足够。

