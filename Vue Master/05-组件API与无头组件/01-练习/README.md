# 练习：可访问的无头 Dialog

## 题 1（90 分钟）

设计 `DialogRoot / DialogTrigger / DialogContent / DialogTitle` 四个组件的公开 API。要求支持受控 `v-model:open`，Escape 关闭，点击遮罩关闭，关闭后焦点回到触发器，打开后焦点进入内容，使用 Teleport，嵌套时只允许最上层响应 Escape。先写状态机和事件表，再写代码。

## 题 2（30 分钟）

Code review：一个业务表单组件有 37 个 props（颜色、权限、请求地址、按钮显隐、校验规则等）。给出拆分方案，但最多拆成 4 层；解释哪些变化轴仍应保留在同一组件，避免“过度原子化”。

