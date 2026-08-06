# 第 12 章练习

## 练习一：为第 04 章搜索写竞态回归测试

使用 Vitest + RTL + MSW（或自建可控 fetch handler）：

- 输入 A，推进 debounce，确认 A 请求开始。
- 输入 B，推进 debounce，确认 B 请求开始/A 收到 abort。
- 先 resolve B，显示 B；再 resolve A，UI 仍是 B。
- B 500 显示错误并可重试；Abort 不显示错误。
- 空查询取消并清空结果。
- StrictMode 下监听/请求没有可见重复副作用。

限制：禁止 `waitForTimeout`、禁止 mock `useUserSearch`、禁止按 class 查询。把测试中发现的生产 API 不可测试点记录下来并重构。

## 练习二：结算流程测试设计（高难）

流程：购物车 → 地址 → 优惠 → 支付确认 → 3DS 外部跳转 → 回跳订单状态。风险有重复提交、价格变化、库存不足、登录过期、回跳伪造、网络中断。

任务：

1. 做风险矩阵，选 8–12 个最值钱用例。
2. 标注每个用例属于纯单元/集成/contract/E2E 哪层，解释为何。
3. 实现至少：金额 reducer 单元、库存/价格 409 集成、重复点击幂等集成、一个 Playwright happy path、一个失败恢复路径。
4. E2E 不用固定 sleep；数据独立；失败有 trace。
5. 给出哪些内容不能仅靠自动化验证（真实支付沙箱、屏幕阅读器、灾备等）。

## 交付

`TEST-STRATEGY.md` 必须写 flake 处理：识别、隔离、owner、修复时限；禁止“加重试就算修好”。

