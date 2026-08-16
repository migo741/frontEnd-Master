# 第 08 章练习

先画凭证、浏览器、应用、身份提供方和数据库的信任边界。不得用“框架帮我处理了”代替协议解释。

## 练习一：可撤销且抗固定攻击的 Session 服务

为多租户运营台实现框架无关的 `SessionService`：密码登录成功后创建 256 bit 随机 session id，数据库仅保存摘要；支持 authenticate、rotate、logout、logoutAll。Cookie 使用 `__Host-session`，写接口另校验 Origin 与 CSRF token。

要求：

1. 给出 PostgreSQL 18 表与约束；同一旧 session 并发 rotate 只能成功一次。
2. idle 30 分钟、absolute 12 小时；触碰频率不得高于每 5 分钟一次。
3. 改密后旧 session 立即无效；数据库或日志中没有可直接重放的 Cookie。
4. 写至少 8 个测试：伪造、过期、固定攻击、并发轮换、重复登出、改密、CSRF、日志脱敏。

验收：业务层不依赖 Fastify/Nest；外部错误不泄漏账号是否存在；所有时间通过注入的 clock 控制。

## 练习二：只能消费一次的 OIDC 回调

实现 Authorization Code + PKCE 回调核心。登录开始时保存 state/nonce/verifier/return path/expiry；回调原子消费事务，再校验 token claims 并创建本地 Session。

攻击场景必须覆盖：错误 state、nonce、issuer、audience、过期 token、`alg=none`、任意 returnTo、同一 callback 并发两次、未知 `kid` 刷新风暴。

验收：只允许相对站内 return path；算法白名单；事务有唯一约束；相同 code/state 最多产生一个 Session；测试不需要真实身份提供方，使用可注入 verifier fake。

## 复写任务

看完答案后关掉文档，从空文件重写“摘要落库 + 原子轮换”和“一次性 OIDC 事务”两条核心路径，并用 200 字解释 state、nonce、PKCE 分别阻止什么。
