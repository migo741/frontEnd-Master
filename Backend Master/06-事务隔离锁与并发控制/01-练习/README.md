# 第 06 章练习

## 练习 1（经典必做）：无负余额、无死锁转账

设计 `wallet(tenant_id, id, balance_cents)` 与 `transfer(...)`：

- 金额使用 bigint 最小单位，必须大于 0。
- 两个钱包必须同租户且不同 ID。
- 总额守恒，任何余额不得为负。
- 一次转账要么两边都更新，要么都不更新。
- 并发相反方向转账按稳定 ID 顺序锁行，不能依赖调用参数顺序。
- 事务内不得调用网络或等待任意外部回调。

用至少 20 个真实并发事务压测，断言最终总额、非负余额和连接池可继续使用。记录余额不足、钱包不存在、deadlock、statement timeout 的失败语义。

## 练习 2（高难）：用 SERIALIZABLE 阻止值班 write skew

表中同一 shift 有两名 on-call 医生。实现 `goOffCall(tenantId, shiftId, doctorId)`，不变量是每个 shift 至少一人仍 on-call。

要求：

1. 先在 REPEATABLE READ 下用 barrier 复现两个事务都成功、最终 0 人的错误。
2. 改为 SERIALIZABLE，让其中一个事务收到 `40001`。
3. 实现完整事务重试：最多 4 次、full jitter、总 deadline；`40001/40P01` 可重试，业务错误和约束错误不可重试。
4. 重试后失败事务重新读取，最终返回 `LAST_DOCTOR`；数据库始终至少一人值班。
5. 每个 attempt 记录 trace 属性，但不能重复任何事务外副作用。

复写时把“至少一人”改为按资格至少一名 `primary`，证明读取 predicate 仍覆盖完整不变量。
