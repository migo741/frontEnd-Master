# 第 06 章练习

只做一个同步协议题和一个真实异步流题。

## 练习 1（经典必做）：懒迭代管道与关闭传播

实现：

```js
pipe(source, map(fn), filter(fn), take(count))
```

要求：

1. 三个 operator 都返回 lazy iterable，不得预先构造数组。
2. map/filter 的回调收到 value 与从零开始的输入索引。
3. take 不得多拉取第 count+1 个值，count=0 时不得取得源 iterator。
4. 消费者 break、回调抛错或 take 达限时，底层 iterator.return 恰好执行一次。
5. 可处理无限序列；同一个结果 iterator 一次性消费的语义要写入文档。
6. 对照原生 Iterator Helpers，说明自写版本仅用于理解协议。

用一个记录 `next`、`return` 调用次数的自定义 iterator 做测试。

## 练习 2（高难）：有界 NDJSON 异步解码器

实现：

```js
async function* decodeNDJSON(byteChunks, {
  signal,
  maxLineBytes = 1024 * 1024,
} = {}) {}
```

`byteChunks` 是 `AsyncIterable<Uint8Array>`，换行由 LF 分隔，可接受 CRLF。

要求：

1. UTF-8 多字节字符可能跨 chunk，不得乱码。
2. 一行可能跨多个 chunk，一个 chunk 也可能含多行。
3. 按行 yield JSON 值，不得先收集完整响应；空白行跳过。
4. 单行超过 maxLineBytes 立即失败，错误含行号；解析失败含安全截断的行摘要。
5. signal 取消、消费者 break、解析错误时，上游 iterator 必须关闭。
6. 不预读下一 chunk，证明下游慢时存在 pull-based 背压。
7. 小输入可用 `Array.fromAsync` 收集测试，但生产流式路径不得物化。

测试必须覆盖 emoji 拆 chunk、CRLF、无末尾换行、超长行、无效 UTF-8、主动取消和早退清理。
