# 第 02 章练习

## 练习一：可观测工具注册器

实现 `@tool(name=..., side_effect=...)`：

- 保留原函数签名、docstring、annotations；拒绝重名。
- 支持同步/异步函数，不允许调用者忘记 await。
- 每次执行记录 duration、成功/失败和 request id，不记录 secret 参数。
- trace 失败不能破坏业务，但要有 fallback 记录策略。
- registry 可列出 metadata，不暴露函数对象给无权限调用者。

## 练习二：可关闭的流式事件管道

实现 generator pipeline：读取大 NDJSON → 解码 → 过滤 → 批处理。要求不把全文件读内存；consumer 提前 break、解析异常和下游异常都关闭文件并记录 span；测试“一次性 iterator 被二次消费”的失败；再设计异步版本的 API 形状。
