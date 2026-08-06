# 第 15 章练习

## 练习一：Modal/富文本评论安全可访问审计

页面有自制 Modal 和 Markdown 评论：div onClick 按钮、无 focus trap、关闭后焦点丢失、评论用 `dangerouslySetInnerHTML`、链接协议不限制。

任务：

- 用键盘、axe、可访问性树和至少一种屏幕阅读器列问题；按严重度排序。
- 改为成熟 Dialog primitive 或补齐语义/focus/Escape/背景 inert/scroll lock；写行为测试。
- Markdown 经可信 parser + allowlist sanitizer；禁止 script/event handler/javascript/data 等非预期协议；设计 CSP。
- 外链、新窗口、图片代理/隐私策略写清。
- 错误/拦截对用户可理解，不把原始恶意内容写日志。
- 给出残余风险与人工测试矩阵。

## 练习二：只在中国区出现的白屏事故（高难）

发布后 15 分钟，部分中国移动网络用户白屏；总体错误率只升 0.2%，但结算成功率降 8%。日志看到少量 `ChunkLoadError`，source map 没符号化，监控 SDK 也在失败 chunk 中。

任务：

- 写前 30 分钟处置时间线：如何判断影响、止血、回滚/flag。
- 设计不依赖主 chunk 的最小错误捕获/静态 fallback。
- 定义需要的 release、route、chunk URL、CDN POP、网络、trace 数据；保护隐私。
- 找至少 4 个假设：CDN 传播、缓存 HTML/资源版本错配、运营商、CSP/域名、资源被删除等，并列证伪手段。
- 修复架构：immutable hashed assets、旧版本保留、原子发布、一次性刷新保护、监控独立性。
- 写 SLO、告警和事后行动项。

答案必须区分“相关性”和“根因证据”。

