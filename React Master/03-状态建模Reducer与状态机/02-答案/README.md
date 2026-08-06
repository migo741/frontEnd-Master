# 第 03 章参考答案

## 练习一：模型

编辑态与结算态互斥：

```ts
type Line = {productId: string; unitPrice: number; stock: number; quantity: number}

type CartState =
  | {status: 'editing'; lines: Record<string, Line>; coupon: 'SAVE10' | null}
  | {status: 'submitting'; lines: Record<string, Line>; coupon: 'SAVE10' | null; requestId: string}
  | {status: 'failed'; lines: Record<string, Line>; coupon: 'SAVE10' | null; message: string}
  | {status: 'completed'; orderId: string}

type CartAction =
  | {type: 'itemAdded'; item: Omit<Line, 'quantity'>}
  | {type: 'quantityChanged'; productId: string; quantity: number}
  | {type: 'couponApplied'; code: 'SAVE10'}
  | {type: 'checkoutStarted'; requestId: string}
  | {type: 'checkoutFailed'; requestId: string; message: string}
  | {type: 'checkoutSucceeded'; requestId: string; orderId: string}
  | {type: 'editingResumed'}
```

所有编辑 action 先检查 `status === 'editing' || status === 'failed'`。生产中可把共同可编辑数据抽为 `CartDraft`，减少重复但保持联合类型：

```ts
type CartDraft = {lines: Record<string, Line>; coupon: 'SAVE10' | null}
```

selector：

```ts
export function selectTotals(state: Exclude<CartState, {status: 'completed'}>) {
  const subtotal = Object.values(state.lines)
    .reduce((sum, line) => sum + line.unitPrice * line.quantity, 0)
  const discount = state.coupon === 'SAVE10'
    ? Math.min(Math.floor(subtotal * 0.1), 10_000)
    : 0
  const discounted = subtotal - discount
  const shipping = discounted >= 19_900 ? 0 : 1_200
  return {subtotal, discount, shipping, total: discounted + shipping}
}
```

金额不进 state，因为它完全由 lines/coupon 推导。服务端结算必须重新计算，客户端 selector 只负责展示。

测试使用表：

```ts
it.each([
  {quantity: -1, expected: 1},
  {quantity: 0, expected: 0},
  {quantity: 99, expected: 5},
])('enforces quantity invariant: $quantity', ({quantity, expected}) => {
  // arrange editing state with stock 5, reduce, assert
})
```

## 练习二：核心转换

```ts
type UploadState =
  | {status: 'idle'}
  | {status: 'ready'; file: File}
  | {status: 'uploading'; file: File; requestId: string; progress: number}
  | {status: 'success'; assetId: string; url: string}
  | {status: 'error'; file: File; message: string}

type UploadEvent =
  | {type: 'fileSelected'; file: File}
  | {type: 'uploadStarted'; requestId: string}
  | {type: 'progressReceived'; requestId: string; progress: number}
  | {type: 'uploadSucceeded'; requestId: string; assetId: string; url: string}
  | {type: 'uploadFailed'; requestId: string; message: string}
  | {type: 'cancelled'; requestId: string}
  | {type: 'retryRequested'}
  | {type: 'reset'}
```

```ts
case 'progressReceived':
  if (state.status !== 'uploading' || state.requestId !== event.requestId) return state
  return {...state, progress: Math.max(state.progress, Math.min(100, event.progress))}

case 'uploadSucceeded':
  if (state.status !== 'uploading' || state.requestId !== event.requestId) return state
  return {status: 'success', assetId: event.assetId, url: event.url}

case 'cancelled':
  if (state.status !== 'uploading' || state.requestId !== event.requestId) return state
  return {status: 'ready', file: state.file}
```

本答案选择“上传中重新选文件：UI 先 abort 当前请求并 dispatch cancelled，随后 fileSelected”。也可规定禁止重新选择；重要的是转换显式且有测试。

AbortController 节省带宽/服务器工作并快速结束等待；requestId 防御取消来不及、服务端仍返回、第三方实现不支持 abort 或竞态已经入队。一个是主动取消，一个是状态正确性的最后防线。

