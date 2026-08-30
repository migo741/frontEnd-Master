# 练习：生产级后台界面

## 题 1（90 分钟）

实现 App Shell：顶栏、可折叠侧栏、主内容、可选 inspector。桌面主区独立滚动，移动端使用动态视口且不产生双滚动；键盘焦点永不被 sticky header/footer 遮住。

要求 sidebar/inspector 开关不由 JS 计算宽度；支持 RTL 和 200% 缩放。

## 题 2（100 分钟）

实现订单表格：sticky 表头/首列、排序、批量选择、长文本、金额、200 行、comfortable/compact 密度；同时完成 loading/empty/error/partial/live 状态。

只有表格容器可横向滚动；视觉顺序与 DOM/表格语义一致；状态切换不得产生明显 CLS。

