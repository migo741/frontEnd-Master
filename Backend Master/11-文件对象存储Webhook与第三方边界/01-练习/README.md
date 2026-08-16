# 第 11 章练习

## 练习一：不会把恶意文件发布出去的上传服务

实现附件申请、直传确认、扫描、下载和删除状态机。对象存储可用 in-memory fake，但接口必须表达 head/version/copy/delete/signedGet；数据库保存 tenant、object id、quarantine/final key、大小、SHA-256、状态和版本。

要求覆盖：伪造 MIME、超限、checksum 错误、扫描超时/恶意、确认重复、扫描后对象被替换、DB 提交失败留下 orphan、删除失败、跨租户下载、过期 upload。禁止把整个文件读入内存。

验收：只有绑定已验证 object version 的 ready 记录可下载；key 服务端生成；签名 URL 最长 60 秒；reconciler 可安全重跑；测试验证主动内容使用隔离域/attachment。

## 练习二：抗重放和乱序的支付 Webhook

实现 raw-body HMAC 验签、5 分钟时间窗、current/previous secret 轮换、event inbox 去重和后台处理。事件有 `eventId/resourceId/resourceVersion/type`；同一资源可能乱序到达。

加入第三方查单 adapter：当缺序或未知状态时拉取权威快照；限制 host、重定向、响应大小与 deadline，抵抗 SSRF。写测试覆盖 body 重序列化、错误签名、窗口内重放、并发重复、版本倒退、DNS/redirect 到内网和查单超时。

验收：HTTP handler 持久化后快速 2xx；签名正确不直接触发退款等高风险动作；同一 event 并发只处理一次；旧资源版本永不覆盖新版本。

## 复写任务

关掉答案，重写对象 promote 的不可变版本检查和 Webhook 原始字节验签；画出“对象已上传但 DB 未提交”与“事件已处理但 2xx 丢失”的恢复路径。
