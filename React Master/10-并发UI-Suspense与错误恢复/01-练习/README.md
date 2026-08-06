# 第 10 章练习

## 练习一：不卡输入的 2 万项检索

给定 20,000 条包含中文/英文的记录和一个故意较慢的评分函数。

要求：

- 输入框每次按键立即反馈；结果区允许落后并标记 stale。
- 先实现 baseline，记录 React Profiler 和 Performance long task。
- 用 `useDeferredValue` 或 Transition 改善调度；再优化算法/索引。
- 不允许用 setTimeout 假装修好；不把昂贵计算放 Effect 再复制结果 state。
- 结果超过 200 行时虚拟化；保持键盘导航/屏幕阅读器策略。
- 写性能预算：测试设备上输入 INP/commit 目标、DOM 节点上限。
- 测试快速输入 abc 时，旧查询结果不会被标成 abc。

回答：为什么 `useMemo` 不能让首次计算变快？为什么 Transition 不能切断一个同步 500ms 函数？

## 练习二：可恢复仪表盘边界树（高难）

页面包含 Header、账户摘要、交易列表、推荐、聊天侧栏。代码和数据延迟不同，推荐可失败，账户鉴权失败必须重新登录，聊天失败不应影响交易。

任务：

- 画 Suspense + Error Boundary 树，标注每个 fallback 和故障域。
- 路由进入时并行启动可并行资源；禁止 parent Effect → child Effect 瀑布。
- 切换账户用 Transition 保留旧页，明确 stale；不能误操作旧账户数据。
- 推荐错误局部重试；401 提升到会话恢复；聊天可关闭。
- skeleton 预留尺寸；定义埋点：边界等待时长、错误、重试结果。
- React 19.2 设计 Activity 预热“交易详情”；再给 React 18 降级。

只需做最小可运行原型和架构说明，不需要精美样式。

