# 答案与复盘

## 题 1 设计要点

`DialogRoot` 持有/代理 open，provide 一个带 Symbol key 的上下文：`open`、`setOpen`、`triggerRef`、`contentRef`、唯一 titleId。Trigger 只处理激活与记录触发元素；Content 负责 Teleport、焦点陷阱、role=dialog、`aria-modal`、`aria-labelledby` 与关闭策略；Title 注册可访问名称。

事件顺序比模板重要：

1. opening：保存当前 activeElement，渲染 content，`nextTick` 后聚焦首个可聚焦项或容器。
2. open：顶层 stack 注册；Tab 在内容内循环；Escape 只由 stack top 处理。
3. closing：从 stack 移除，卸载后把焦点还给仍在文档中的 trigger。

遮罩判断应使用 `event.target === event.currentTarget`，否则点击内容也关闭。SSR 下访问 document 必须延迟到 mounted。生产实现还要处理滚动锁的引用计数、嵌套 Teleport、初始 focus、动画结束时机。若这些边界无法充分测试，优先采用成熟且可访问性经过验证的 headless library，而不是自造基础设施。

## 题 2

一个合理的四层：页面容器负责请求、权限与路由；`OrderForm` 负责领域草稿、验证与 submit 事件；design-system 表单控件负责视觉/交互；策略对象或 composable 负责权限和字段配置。颜色归 design token，请求地址归 repository，按钮是否展示多由能力/状态派生，不应都是 prop。

不要把每个 label、icon、校验提示都拆成业务组件。共同变化、必须共享状态机且不会独立复用的部分留在一起。拆分标准是变化原因和契约清晰度，不是文件越小越高级。

