# 练习：接管第三方样式而不打军备竞赛

## 题 1（45 分钟）

给一个按钮同时加载 user-agent、reset、第三方库、业务组件、utility、行内 style 和 reduced-motion 规则。逐项写出 `color`、`padding`、`transition` 的最终值与淘汰顺序，再用 DevTools 截图验证。改变文件加载顺序后，结论也必须解释得通。

限制：第一遍不能运行代码；必须先预测。

## 题 2（60 分钟）

把一份依赖 14 个 `!important`、ID 和十层后代选择器的旧表单迁移到 `@layer reset, vendor, base, components, utilities, overrides`。视觉保持一致，常规组件选择器不高于 `0-2-0`，至少正确使用一次 `:where()` 和一次 `revert-layer`。

验收：调换物理 CSS 文件加载顺序，结果仍一致；新增 danger variant 不提高旧选择器权重。

