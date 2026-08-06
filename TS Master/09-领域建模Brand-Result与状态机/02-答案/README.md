# 第 09 章参考答案

## 练习一

```ts
declare const brand: unique symbol
type Branded<T, B extends string> = T & {readonly [brand]: B}
type UserId = Branded<string, 'UserId'>
type ProductId = Branded<string, 'ProductId'>

type Currency = 'CNY' | 'USD'
type Money<C extends Currency> = Readonly<{minor: bigint; currency: C}>

function add<C extends Currency>(a: Money<C>, b: Money<NoInfer<C>>): Money<C> {
  if (a.currency !== b.currency) throw new Error('Currency mismatch')
  return {minor: a.minor + b.minor, currency: a.currency}
}
```

`NoInfer` 防 b 把 C 推成宽 union；runtime check 防 JS/反序列化/断言调用者。构造：

```ts
function parseUserId(raw: string): Result<UserId, IdError> {
  return /^usr_[a-z0-9]{6,}$/.test(raw)
    ? {ok: true, value: raw as UserId}
    : {ok: false, error: {kind: 'invalid-user-id'}}
}
```

断言仅在构造器验证后。Money Wire `{minor:'1234',currency:'CNY'}`，parse 检查十进制整数格式、范围、currency allowlist，再 BigInt。convert 使用有理数 numerator/denominator 或 decimal 库，明确 half-up/bankers/floor，不能直接 number 乘。

## 练习二

State 采用判别联合，每个变体含 `version` 与必要金额/ID。Command 至少含 `operationId`、`expectedVersion`，但 transition 纯函数无法保证跨请求唯一：持久层需 operationId 唯一约束/幂等表，expectedVersion 用 compare-and-swap/事务。

退款：Paid state 可含 `refunded: Money<C>`；refund command 金额 >0，且 `refunded + amount <= paidTotal`，同币种检查。成功增加 version，产生 domain event；外部支付调用应由 outbox/幂等 worker，不放纯 reducer。

Wire decoder 对未知 `status` 返回 `{kind:'unsupported-version', rawStatus, schemaVersion}`，不强断言成 never；可阻止操作并提示升级。静态 assertNever 只覆盖本版本已解析 Domain union。

支付“只一次”是分布式副作用，类型在单进程编译期无法阻止重试、双实例、网络超时后未知结果；需要服务端幂等 key、数据库唯一/事务、供应商幂等和对账。

