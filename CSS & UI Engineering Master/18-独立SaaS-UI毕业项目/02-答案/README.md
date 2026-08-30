# 评审答案与复盘

毕业项目没有唯一截图答案。以下是必须逐项指向代码、测试或证据的评审门禁。

## CSS 机制

- 是否能从 DevTools 解释任一最终值的 cascade 路径？
- 是否消除了随机 z-index、无 owner important、固定内容高度？
- Grid/Flex/flow/container query 是否根据关系选择，而非个人偏好？
- 新 CSS 被关闭时，任务是否仍可完成？

## 产品韧性

- loading/empty/error/partial/stale/permission/long text 是否有真实 fixture？
- 320px 和 400% zoom 除二维数据区外是否无双向滚动？
- RTL 是否只靠逻辑属性/token/少量图标规则完成？
- 主题、密度、品牌变化是否不复制组件 CSS？

## 无障碍

- DOM 顺序是否等于任务顺序？焦点清晰且不被 sticky/overflow 裁切？
- forced-colors、reduced-motion、键盘、触摸目标是否人工通过？
- 错误、状态、图表是否不只依赖颜色？自动工具是否无 serious/critical？

## 生产交付

- 视觉 baseline 是否在固定环境生成并经过人工审查？
- CSS/字体/图片是否有预算、waterfall 和 CLS 证据？
- 是否有三个最小复现记录，说明如何从症状走到根因？
- ADR 是否说明被拒方案、代价和复审条件？

## 最终闭卷复写

从空文件重写：layer 顺序与低权重 Button；含长文本的 Grid/Flex 卡片；容器查询订单摘要；light/dark semantic tokens；可见 focus/forced-colors；一个具 fallback 的渐进增强。随后用 15 分钟口述它们共同解决的问题：让内容、用户环境和系统变化发生时，界面仍然正确。

