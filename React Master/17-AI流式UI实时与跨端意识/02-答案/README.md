# 第 17 章参考答案

## 练习一：协议处理流水线

```text
ReadableStream bytes
 -> TextDecoder(stream=true)
 -> NDJSON/SSE parser（保留 incomplete buffer）
 -> schema validation
 -> sequence/dedupe/gap detector
 -> per-turn event reducer
 -> text delta buffer (32ms/frame)
 -> normalized conversation store
 -> React selectors
```

归属检查必须在 reducer 前：event.conversationId/turnId 匹配已知会话；Abort 后仍到达的事件只有当 sequence/attempt 仍有效才接受。EventId Set 可限制窗口，sequence <= last 忽略，> last+1 暂停应用并请求 resume/snapshot。

Parser 核心：`decoder.decode(chunk, {stream:true})` 累加字符串；只消费完整分隔行，剩余保留下次；流结束 `decoder.decode()` flush。生产协议还要限制单事件/缓冲区大小，防内存攻击。

UI 更新缓冲独立于协议接收：事件仍按序进入领域模型，但多个 text delta 合成一个 patch。Stop 立即改变本地 status 为 cancelling，abort transport 并发 cancel endpoint；收到 ack/终止后 cancelled，超时显示“不确定，刷新状态”。

## 练习二：优化顺序

1. Store 规范化：历史完成消息引用稳定，只有当前 turn part 改。
2. 32ms/animation frame 合并文本，100 update/s 降为约 25–30 commits/s。
3. 已完成 Markdown 缓存 AST/render；流式尾部只解析不稳定段，完成时做最终 parse。
4. 虚拟化只挂可视消息 + overscan；用 measured height cache，图片 load 后修正并保持锚点。
5. 是否跟随用“距离底部阈值”而不是每 token `scrollIntoView`。用户离开底部后仅计数新内容。

profile 应区分 Markdown JS、React render、layout/scroll。若 layout 是瓶颈，进一步减少同步高度测量/scroll 次数；若 parser 是瓶颈，可 Worker 解析非 DOM 数据。

跨端共享：protocol schemas、event reducer、API client（抽 transport）、query keys、domain tests；Web 用 DOM/Markdown renderer/IntersectionObserver，RN 用 Text/View/FlatList、原生 Markdown 或自定义 renderer、AppState/安全存储。FlatList 动态高度/倒序列表和后台 socket 暂停需平台实现，不能直接共享 Web 虚拟化代码。

