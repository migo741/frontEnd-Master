# 第 09 章练习

## 练习一：不会误触的动态任务命令列表

实现一个可动态增删行的任务列表。每行包含任务标题、完成 checkbox、打开详情 button 和删除 button；按钮内部有 SVG 图标。

要求：

- 列表根节点只注册一个 click listener，以 `data-action` 路由 open/delete；
- 用 `closest` 与 `contains`，点击 SVG/path 与点击按钮文字结果相同；
- 点击 checkbox 只改变完成状态，不能误触打开详情；
- 新增行无需新增 listener；任务 id 不可信时不得拼进 `innerHTML`；
- 控制器接收 AbortSignal 或返回 `dispose()`，卸载再挂载不会重复执行；
- button 的 Enter/Space 原生工作，焦点样式清楚，不使用正 tabindex；
- 测试无关空白点击、嵌套图标、动态行、删除后焦点落点和清理。

验收：事件解析函数与 `openTask/deleteTask` 领域命令可分别测试；不靠在每个子元素上调用 `stopPropagation`。

## 练习二：可靠的原生模态确认框（高难）

基于 `<dialog>` 实现“删除项目”确认框：

- 由多个不同 opener 复用，打开时记录实际触发者；
- 对话框有可访问名称、危险说明、取消与确认按钮；
- 首次焦点落在取消按钮；Tab 不逃到背景，Escape 等价取消；
- 点击真实 backdrop 取消，点击 dialog 内容/内边距不能误关；
- 提交期间防重复，服务端失败后保持打开并把错误与确认按钮关联；
- 关闭后恢复到仍在 DOM 的 opener；若 opener 已删除，回到项目列表标题；
- dispose 时释放 listener，并处理对话框恰好打开的情况；
- 用键盘测试完整流程，并在 Accessibility tree 验证 name/role/state。

先写状态转换：closed → open → submitting → error/closed。不要把所有状态藏在 CSS class。

## 复盘交付

从一个你写过的 React/Vue 组件中挑出一次 `stopPropagation`，说明它是在表达业务命令边界，还是在掩盖模糊的 DOM 交互结构。
