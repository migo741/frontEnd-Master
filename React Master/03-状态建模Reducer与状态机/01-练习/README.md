# 第 03 章练习

## 练习一：购物车领域 Reducer

业务规则：

- 商品以 `productId` 唯一；重复添加增加数量。
- 数量必须为 1..库存；设为 0 表示移除。
- 优惠码 `SAVE10` 对商品小计打九折，但总优惠最多 100 元。
- 运费不存入 state：折后商品额满 199 免运费，否则 12 元。
- 结算开始后购物车不可编辑；失败可恢复编辑，成功进入完成态。

任务：

1. 设计能排除 `checkingOut && completed` 这类非法组合的 state。
2. Action 必须是领域事件，例如 `itemAdded`，禁止 `setTotal`。
3. 实现纯 reducer；金额全部用“分”表示，避免浮点误差。
4. totals 用 selector 派生，不能放 state。
5. 写表驱动测试覆盖库存边界、重复添加、优惠上限、结算态拒绝编辑。

限制：不使用外部状态库；不要在 reducer 生成随机 id、读时间或请求。

## 练习二：可取消上传状态机（高难）

构建单文件上传模型：

- 状态：idle、ready、uploading、success、error。
- 事件：fileSelected、uploadStarted、progressReceived、uploadSucceeded、uploadFailed、cancelled、retryRequested、reset。
- 旧请求的 progress/success 不能更新新请求，action 中带 `requestId`。
- 上传中重新选文件的策略由你决定，但必须写成显式规则并测试。
- error 状态保留 file 以便 retry；success 只保留必要的 asset 信息。

先只写纯状态机和测试，再接 UI。UI 中 AbortController 放 ref，网络副作用不能进入 reducer。

至少回答：取消请求和“忽略旧响应”为什么两者都要做？

## 交付物

- `cartReducer.ts`、`cartSelectors.ts`、测试；
- `uploadMachine.ts`、测试；
- `state-model.md`：画状态转移表并列出 5 个不变量。

