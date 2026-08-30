# 答案与复盘

## 题 1

状态至少拆为 open、query、composition、request status/version、highlightedId、selectedIds。IME compositionstart 到 compositionend 期间不触发搜索；搜索采用 latest-wins。键盘：Arrow 移动、Enter 选择、Escape 分层关闭、输入为空时 Backspace 删除最后 chip；highlighted option 用稳定 id 连接 `aria-activedescendant`。

角色与关系：input 使用 combobox 语义、`aria-expanded/controls/autocomplete`；popup 为 listbox，多选标记 multiselectable；option 暴露 selected；loading/error 用合适 live region，但避免每个按键都吵闹。虚拟化时 active option 必须在 DOM，移动高亮先滚入窗口；若无法保证读屏体验，应提供非虚拟化阈值或替代模式。

状态转换示例：closed→typing open；typing→composing 不请求；compositionEnd→loading；loading(v1)→loading(v2) abort v1；loading→results/error；open+Escape→closed；open+Enter→selected；selected+Backspace→removed。

## 题 2

先在同一 major 新增新 API，旧 `type` 通过 adapter 映射并开发环境一次性告警；遥测或静态扫描统计剩余调用。提供 AST codemod，将已知值安全转换，动态表达式输出 TODO 而不是猜。文档和新示例只用新 API，CI 阻止新增旧调用。

一个或两个 minor 后，当主仓库和关键消费者归零，再在下一个 major 删除旧 API；发布 migration guide 和 visual diff。删除条件应基于消费数据、迁移工具成功率和支持窗口，不是“已经提醒过”。样式 token 变化需视觉回归，因为 TS 不会发现颜色对比度和布局破坏。

