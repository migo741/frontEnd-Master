# 第 17 章练习

## 练习一：可中断、可恢复的流式聊天

使用 fake server 或本地 endpoint，协议为 NDJSON/SSE 均可。

要求：

- 事件：turn.started、text.delta、tool.started/completed、turn.completed/failed；含 eventId/sequence/turnId。
- parser 处理一个 JSON 被拆成多个 chunk、多个事件同 chunk、UTF-8 中文截断。
- 每 32ms 批量提交文本；Stop abort，并等待/展示服务端 cancel ack。
- 快速切 conversation 时旧事件不污染新会话。
- 断线按 last sequence 恢复；重复事件幂等；缺口拉 snapshot。
- Markdown 安全净化；工具卡不执行模型生成代码。
- 测试半包、乱序/重复、断线、取消竞态、StrictMode、长输出。

指标面板显示 TTFT、tokens/s、render lag（开发模式即可）。

## 练习二：每秒 100 token 的长对话性能（高难）

模拟 1,000 条历史消息 + 当前流 100 token/s，消息含代码块、图片占位、工具卡。

任务：

- baseline 每 token setState + 全量 Markdown，profile。
- 实现 buffer/批量、稳定 part、尾消息局部解析、虚拟化。
- 用户在底部自动跟随；上滑后不抢滚动；点击“回到底部”恢复。
- 图片加载改变高度后锚点不跳；键盘/搜索结果仍可定位。
- 设内存/DOM/INP/commit 预算，输出 before/after。
- 设计 React Native 迁移边界：哪些包共享、哪些平台实现；说明 FlatList/应用后台的额外问题。

不要求追求最好数字，要求所有结论可复现。

