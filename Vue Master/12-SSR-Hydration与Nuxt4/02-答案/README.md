# 答案与复盘

## 题 1

- 随机 id：两端不同导致 label/for 和节点属性 mismatch；使用 Vue `useId()` 或由数据提供稳定 id。
- locale：服务器时区/locale 与浏览器不同；传入明确 locale/timeZone，或服务端输出 ISO，mounted 后格式化局部文本。确实不可避免才精确标注允许的 text mismatch。
- 宽度：服务端没有 viewport；用 CSS media query 负责纯布局，或两端先输出相同默认结构，mounted 后增强。
- 顶层 Pinia：进程复用时用户 A 状态可能进入 B 响应；export factory，每个请求创建并序列化自己的实例。

`ClientOnly` 全包会牺牲 SSR 内容和首屏价值，也掩盖模型问题。

## 题 2

cache key 至少包含 tenantId、user permission scope、ticketId、数据版本/locale 等实际输出维度；私有数据用 per-request/request-scoped cache，响应 `private/no-store` 或合适私有策略，绝不放公共 CDN key。

服务端路由解析 → 验证会话/权限 → `useAsyncData` 以稳定 key 取数 → 403/404 设置正确 HTTP status → payload 安全序列化 → 客户端 hydrate 复用 payload。客户端 id 改变时旧 fetch abort，key 随 id 变化。mutation 成功精准更新当前实体后 refresh/invalidate 对应 key；不要 `watchEffect` 再发第二份重复请求。

验证需包含两个并发 SSR 请求使用不同用户，断言 HTML/payload 不串数据；这比只测单请求更能发现全局单例事故。

