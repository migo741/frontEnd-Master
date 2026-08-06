# 第 03 章练习

## 练习一：不可信 WebSocket 事件路由

事件协议：

```ts
type Event =
  | {type: 'ticket.created'; payload: {id: string; title: string}}
  | {type: 'ticket.assigned'; payload: {id: string; assigneeId: string}}
  | {type: 'heartbeat'; payload: {sequence: number}}
```

任务：

- 输入从 `unknown` 开始，写最小 decoder；未知 type 返回 `unknown-event`，坏 payload 返回带 path 的错误。
- decoder 成功后，handler switch 穷尽；新增 `ticket.closed` 时必须产生编译错误。
- 不使用 `as Event`、`any` 或只检查 `type` 就返回 predicate。
- heartbeat sequence=0 是合法值，禁止真值误判。
- 写正负测试和一条旧客户端收到新事件的兼容策略。

第 10 章会用 Schema 库重写；本题先理解证明责任。

## 练习二：可组合 Reducer 的穷尽性（高难）

订单 action：itemAdded、couponApplied、checkoutStarted、checkoutSucceeded、checkoutFailed、reset。

要求：

- State 与 Action 都使用判别联合，排除 completed 仍带可编辑 cart 的非法状态。
- reducer 对“某状态下不允许的 action”返回领域错误，而不是静默 state。
- 建立 `transition(state, action): Result<State, TransitionError>`。
- 每个 state/action 组合有表驱动测试；类型层新增 action 时处理表/实现必须报错。
- 比较单一大 switch、按 state 分派、handler map 三种方案的穷尽性和可读性。

限制：不能用 `Record<Action['type'], (state:any, action:any)=>any>` 假装类型安全。

