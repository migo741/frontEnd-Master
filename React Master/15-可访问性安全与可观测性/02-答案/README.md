# 第 15 章参考答案

## 练习一：优先级

P0/P1：未净化 HTML 导致存储型 XSS；Modal 无法键盘退出/焦点逃到背景；伪按钮键盘不可用。P2：关闭焦点不恢复、名称/描述缺失、滚动锁/阅读顺序问题。自动 axe 不能证明 focus trap 和屏幕阅读器体验正确。

生产优先 React Aria/Radix 等经过审计 primitive，外层品牌组件限制 API。测试：打开后 dialog 有名称、焦点在合理元素、Tab 不离开、Escape 关闭、关闭后回 trigger、背景不可交互、嵌套/卸载 trigger 有 fallback。

Markdown pipeline：禁 raw HTML 或 parse AST → allowlist 元素/属性 → URL protocol allowlist（通常 http/https/mailto 按需求）→ sanitizer；渲染后仍用 CSP 限制 script/connect/img/frame。data URL 图片、SVG、远端图片可追踪用户/IP，按产品做代理/允许域。日志只记拦截规则 id、内容 hash/长度、用户/trace 的脱敏标识，不能存恶意全文和 token。

## 练习二：处置

前 5 分钟按 release/地区/运营商/route 切片确认结算下降与新发布相关；暂停发布，通过 feature flag/流量切回上一稳定入口或回滚 HTML，确保旧 assets 仍存在。5–15 分钟验证 CDN/源站命中和 chunk 可达，抽样不同 POP/网络，通知业务/客服。15–30 分钟选最小安全修复，灰度并观察 chunk 成功率与结算恢复。

假设与证据：

- HTML 指向已删除旧 chunk：失败 URL 对象存储 404、HTML/cache age 与 release 不匹配。
- CDN 传播/POP 异常：按 POP 响应码/age/hash 聚类，源站正常。
- 运营商/DNS/TLS：同 POP 不同网络对比，连接阶段 trace。
- CSP/域名变更：浏览器 violation report/console，响应头差异。
- chunk 内容损坏：hash/SRI/字节范围与源产物比对。

`ChunkLoadError` 与新发布同时出现只是相关；必须由 404/缓存版本/POP 等证据闭环。

架构：content-hashed immutable assets 先全量上传并验证，再原子切 HTML；保留至少覆盖最大 HTML/CDN/Service Worker TTL 的旧 assets；入口内联极小 fallback 捕获 script load 并展示恢复，session 标记只 reload 一次；遥测 endpoint/最小脚本独立于主 chunk。告警以结算成功率、入口 JS 加载成功率、地区/运营商错误预算为核心，总体 0.2% 会掩盖 cohort 灾难。

