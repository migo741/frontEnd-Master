# 练习：生产表单与不会被裁切的菜单

## 题 1（75 分钟）

实现账户设置表单完整状态矩阵：文本、select、checkbox、radio、range；覆盖 focus、disabled、readonly、invalid、autofill、loading。仅键盘可完成保存，400% 缩放和 forced-colors 可用。

限制：placeholder 不得代替 label；错误不得只靠红色；触控目标约 44×44 CSS px。

## 题 2（70 分钟）

实现跟随按钮的操作菜单与确认 dialog。菜单靠近四个视口边缘时选择合理位置；优先使用 Popover + Anchor Positioning，提供不支持 anchor 时的 fallback。滚动、缩放、RTL 后仍不离开触发关系。

