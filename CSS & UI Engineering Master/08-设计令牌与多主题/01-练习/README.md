# 练习：建立可换品牌的语义主题

## 题 1（70 分钟）

把一个含 86 个硬编码颜色/间距的 Dashboard 重构为 primitive、semantic、component 三层 token。支持 light/dark，组件不得直接引用 primitive color；状态不能只靠颜色区分。

验收：新增“高对比暗色”只改 token 和少量系统规则，不复制组件 CSS；正文、控件、焦点达到课程对比要求。

## 题 2（50 分钟）

实现两个租户品牌 + 系统/手动主题。SSR 首屏不得先亮后暗；localStorage 不可用时仍能回退；forced-colors 下按钮、边界、选中、禁用和焦点仍能区分。

提交主题优先级表：用户显式选择、系统偏好、租户默认谁胜谁。

