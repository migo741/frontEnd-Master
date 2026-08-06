# 第 16 章参考答案

## 练习一：协调

- c：同级能以 key=c 找到同 type `Row`，Fiber/Hook state 可复用；位置从 3 到 1，DOM 可能移动，label 更新为 C2。
- b：key 相同但 type 从 Row 变 SpecialRow，旧 b 子树卸载、新 b 子树挂载，局部 state 重置。
- d：不存在旧匹配，新建/placement。
- a：新集合未使用，删除并运行 cleanup/ref null。

WIP 计算这些 flags，不应在 render 直接操作 DOM；commit 批量执行删除/placement/update，随后相应 effects。

更新队列中同步替换和 Transition 函数更新可能被分优先级处理。在 React 18/19 常见的离散事件语义下，紧急 render 先处理“替换为 1”，跳过 Transition 的 `+10`，再处理紧急 `+2`，所以先提交 3；后续 Transition render 从正确的 base state 重放 `+10` 和跳过之后克隆保留的 `+2`，最终为 13。base queue 不能只丢掉“已经处理过”的 `+2`，否则低优先级重放会错误得到 11。请仍用你锁定的具体 React 版本写测试，并明确事件/Transition 边界；公开保证是更新顺序与一致性，私有 lane/队列字段不是 API。

## 练习二：合格报告模板

```md
# 问题（React vX.Y.Z / commit ...）
## 公开契约（官方文档链接）
## 最小实验与结果
## 从入口到关键分支的调用图
## 快照/队列/flags 的必要字段
## 官方测试如何覆盖边界
## 我的初始假设为何错误
## 结论：可依赖语义 vs 私有实现
## 未确认与下个实验
```

以 `useSyncExternalStore` 为例，报告应围绕“subscribe/getSnapshot 协议、render 读取、commit 前/后检查、store consistency、SSR snapshot”，而不是罗列所有 reconciler 文件。需要验证 store 在 render 与 commit 间改变时，React 最终 commit 是否包含一致 snapshot；并说明 getSnapshot 必须缓存，否则协议本身被破坏。

源码会变化，本答案不提供易过期的行号。应从 [React GitHub 仓库](https://github.com/facebook/react) 固定 tag，搜索 Hook 公共导出、reconciler 实现与同名测试，并引用你实际阅读的永久链接。
