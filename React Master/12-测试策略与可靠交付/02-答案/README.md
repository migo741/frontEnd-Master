# 第 12 章参考答案

## 练习一：可控顺序

核心不是完整样板，而是把 Promise 控制权放测试：

```ts
function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej })
  return {promise, resolve, reject}
}
```

MSW handler 为 q=A/B 分别等待 deferred；测试输入、推进 timer，然后按 B → A resolve。由于 fetch Response 构造较繁琐，也可让 handler 等 gate 后返回 `HttpResponse.json`。

```tsx
const user = userEvent.setup({advanceTimers: vi.advanceTimersByTime})
render(<StrictMode><SearchPage /></StrictMode>)

await user.type(screen.getByRole('searchbox', {name: '用户'}), 'A')
await vi.advanceTimersByTimeAsync(300)
// 清空并输入 B，推进，release B gate
expect(await screen.findByText('B User')).toBeVisible()
// release A gate
expect(screen.queryByText('A User')).not.toBeInTheDocument()
```

不要断言 `setState` 未调用；最终 UI 和 abort 记录更接近契约。测试后 `server.resetHandlers()`、恢复 real timers。

## 练习二：风险矩阵样例

| 风险 | 影响 | 测试层 |
|---|---:|---|
| 金额/优惠计算错误 | 极高 | 纯 reducer + property/table tests |
| 服务端价格变化 | 高 | API contract + 组件集成 409 |
| 双击重复订单 | 极高 | 服务端幂等集成，E2E 辅助 |
| 库存不足 | 高 | 集成，错误就近且购物车可修改 |
| 登录过期 | 高 | 路由/集成，安全回跳 |
| 3DS 回跳被伪造 | 极高 | 服务端集成/安全测试；前端只查权威状态 |
| 网络中断 | 高 | 集成 + E2E offline/recovery |
| 样式/焦点错误 | 中 | RTL/axe + 键盘人工/E2E |

E2E happy path 只验证系统接线：通过 API 建购物车/账号，UI 完成地址/确认，拦截或使用支付沙箱，回跳后轮询权威订单状态。不要在前端相信 `?success=true`。

重复点击测试必须检查两次传输使用同一 idempotency key 且服务端只产生一个订单；只断言按钮 disabled 不够。

自动化难覆盖真实银行/支付供应商故障、不同屏幕阅读器实际体验、全区域灾备、生产 CDN/网络长尾；需要沙箱契约、人工演练、混沌/灾备和生产监控补充。

