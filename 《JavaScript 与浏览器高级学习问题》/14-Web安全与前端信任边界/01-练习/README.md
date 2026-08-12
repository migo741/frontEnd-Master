# 第 14 章练习

## 练习一：评论预览的纵深 XSS 修复

遗留页面把 Markdown 渲染结果和 URL 参数直接写入 DOM：

```js
preview.innerHTML = renderMarkdown(new URLSearchParams(location.search).get('text') ?? '')
profileLink.setAttribute('href', user.profileUrl)
```

任务：

1. 构造至少三种不同上下文的攻击：事件属性/危险标签、`javascript:` URL、第三方 Markdown 插件输出；
2. 在保留“有限富文本”需求的前提下分层修复：安全 URL 解析、成熟 sanitizer、最小 DOM sink；
3. 给出 strict CSP 的 Report-Only 到强制上线方案；目标浏览器支持时加入 Trusted Types；
4. 写自动化测试，证明普通文本、允许标签、被拒绝标签和危险 URL 的结果；
5. 列出 sanitizer 配置升级、CSP 违规和误杀的监控方法。

禁止用正则删除 `<script>`；禁止把用户内容全部改成纯文本来回避既定富文本需求。

## 练习二：支付 iframe 消息协议（高难）

父页面嵌入 `https://pay.example-pay.cn`，当前实现为：

```js
window.addEventListener('message', e => {
  if (e.origin.endsWith('example-pay.cn') && e.data.type === 'paid') {
    showSuccess(e.data.orderId)
  }
})

frame.contentWindow.postMessage({type: 'pay', orderId}, '*')
```

设计并实现安全协议：

- 精确 origin 与 `event.source` 校验；
- 发起支付时生成一次性 channel nonce，消息带版本、requestId、nonce；
- 对消息做运行时 schema 校验并限制大小；
- 防重复、过期和乱序；页面只把 iframe 消息当提示，最终状态由同源后端确认；
- frame 超时、导航到其他 origin、重复回调、用户取消都有明确状态；
- 给出至少六个攻击/故障测试。

交付一张威胁模型：攻击者能力、资产、入口、防护层、剩余风险。

