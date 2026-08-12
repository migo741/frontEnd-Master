# 第 11 章练习

## 练习一：可验证的 ETag 文档加载器

实现 `createDocumentLoader({fetchImpl, timeoutMs})`，对同一 URL 保存最近一次成功文档与 ETag。

要求：

- 首次 GET 正常请求；有 ETag 时发送 `If-None-Match`；
- 200 必须检查 JSON Content-Type，再解析并保存；无 ETag 时仍可返回但下次不能伪造验证；
- 304 复用已有文档，绝不调用 `response.json()`；无本地条目收到 304 视为协议错误；
- network、abort、http、decode/protocol 错误可区分，错误带限长 request id；
- 用户 signal 与超时组合，结束后清 timer/listener；
- cache key 至少包含规范化 URL 与影响表示的 Accept/身份维度；
- 文档按不可变值消费，调用者不能篡改缓存中的对象；
- fake fetch 测试 200→304、ETag 变化、坏 Content-Type、500、超时和用户取消。

完成后解释：为什么生产中应尽量让标准 HTTP cache 完成 revalidation，而不是每个组件自造这层 Map？

## 练习二：可恢复的实时库存序列（高难）

实现与传输无关的 `SequencedInventory`，接受：

```js
{type: 'snapshot', sequence: 40, items: [...]}
{type: 'upsert', sequence: 41, item: {...}}
{type: 'remove', sequence: 42, id: 'sku-1'}
```

要求：

- sequence 重复/旧消息幂等忽略；连续消息提交；发现缺口立即标 stale 并请求 snapshot；
- 缺口期间缓冲有固定上限，snapshot 到达后丢旧、按序 drain；仍有缺口继续恢复；
- item id 重复、未知事件、非法 sequence 进入 protocol error，不污染当前快照；
- 对外快照不能暴露内部可变 Map；
- WebSocket 适配器有 AbortSignal、心跳、full-jitter 重连和 resume sequence；
- 缓冲超限关闭连接并全量恢复，不无限吃内存；
- fake transport 注入重复、乱序、缺口、迟到 snapshot、断线和消息风暴；
- 指标包含 sequence lag、duplicates、gap recoveries、buffer high-water 与 reconnects。

不要求写 UI，也不要实现 NDJSON parser；本题只训练实时一致性协议。

## 复盘交付

画出“HTTP snapshot + WebSocket delta”的加载序列，并指出至少三个“socket 显示 connected，但页面数据仍不可信”的时刻。
