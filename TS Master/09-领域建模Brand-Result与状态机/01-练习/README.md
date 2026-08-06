# 第 09 章练习

## 练习一：不串 ID、不串币种的结算

设计 UserId/ProductId/OrderId 与 `Money<'CNY'|'USD'>`。

要求：

- ID 只能由格式验证构造；UserId 不能传 Product API。
- Money minor 用 bigint；同币种可 add/subtract，不同币种编译失败且运行时也检查。
- `convert` 需要显式汇率、目标币种、舍入模式，返回 Result。
- Wire DTO 用字符串传 bigint，Schema 恢复 Brand/Money。
- 负数、溢出/上限、未知 currency、非法 decimal 有测试。
- 禁止业务代码 `as UserId/as Money`。

## 练习二：订单状态机（高难）

状态：draft → submitted → paymentPending → paid；draft/submitted 可 cancel；paymentPending 超时可回 submitted；paid 可 refund（部分/全部）。

要求：

- 类型排除每个状态不相关字段。
- Command 判别联合；transition 返回 Result，新状态携带 version。
- operationId/idempotency 和 expectedVersion 进入命令协议。
- 部分退款累计不能超过实付金额；这是运行时不变量。
- 保存/加载通过 Wire DTO，未知未来状态兼容处理。
- 画状态表并用 property-based 或表驱动测试覆盖所有边。

回答：为什么仅用类型不能保证支付只执行一次？

