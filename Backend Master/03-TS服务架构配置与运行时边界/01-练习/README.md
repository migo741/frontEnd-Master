# 第 03 章练习

## 练习 1（经典必做）：一次性配置编译器

实现 `loadConfig(env)`，将 `Record<string, string | undefined>` 编译成冻结配置：

- `APP_ENV`: `development | test | production`；必填。
- `APP_PORT`: 1–65535 的十进制整数；默认 3000。
- `APP_DATABASE_URL`: 必填 PostgreSQL URL；生产禁止无 TLS 参数。
- `APP_LOG_LEVEL`: `debug | info | warn | error`；默认 `info`。
- `APP_MODEL_API_KEY`: 必填，返回 `SecretString`，JSON/inspect 时必须脱敏。

不变量：聚合返回所有配置错误；拒绝未知 `APP_*`；不修改输入；输出不可变；禁止 `Boolean(string)`、宽松 `parseInt` 和散落的 `process.env`。

测试至少覆盖空字符串、`3000x`、越界端口、未知键、错误协议、生产无 TLS、秘密脱敏和多个错误同时出现。

## 练习 2（高难）：框架无关的创建工单用例

实现一条 `POST /tickets` 垂直切片：

1. HTTP body 从 `unknown` 开始，只允许 `{ title, priority }`，拒绝额外字段。
2. `tenantId/userId` 只能由 adapter 的可信 auth context 注入；body 携带 `tenantId` 必须失败。
3. application 用例只依赖 `TicketWriter`、`Clock` 和 `IdGenerator`。
4. domain/application 不得导入 Fastify、NestJS、`pg` 或 `process.env`。
5. 可控输入错误映射 `422`；未识别 repository 错误映射脱敏 `500`。
6. fake 依赖测试必须精确证明写入的租户、创建者、时间和 ID。

交付：目录依赖图、实现、单元测试、一个不超过 15 行的 Fastify adapter，以及错误映射表。

复写时把 Fastify adapter 换成队列 consumer；application 文件不得修改。
