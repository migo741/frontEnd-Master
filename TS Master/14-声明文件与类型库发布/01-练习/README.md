# 第 14 章练习

## 练习一：发布 `@acme/codec`

实现并发布一个无依赖 codec 库：

- `@acme/codec` 导出 `Codec<T>`、`object`、`array`、`literal`、`union`；
- `@acme/codec/json` 导出 JSON parse/stringify 辅助；
- 支持 ESM 与 CJS，生成声明和 declaration maps；
- `Infer<typeof schema>` 能获得输出类型，但公共错误信息不能无限展开；
- internal AST 不得出现在消费者可导入 API；
- CI 用 TypeScript 5.9 与 6.0、两个 Node 版本和 Vite fixture 验证 tarball。

列出你认为属于 major 的 5 种“只改类型”变更。

## 练习二：给遗留 JS 插件补类型（高难）

有一个 CommonJS 包：

```js
function createClient(options) { /* ... */ }
createClient.defaults = { timeout: 5000 }
createClient.Client = Client
module.exports = createClient
```

插件会在 runtime 调用 `client.use(plugin)` 后注册 `client.cache.get/set`，未注册时不存在。

要求：

- 为原包写准确 `.d.ts`，包含 callable object、property、class。
- 设计插件类型，避免让所有 Client 在未注册插件时都“凭空拥有” cache。
- 写正向/负向类型测试和 runtime 对齐测试。
- 说明 `esModuleInterop` 只改变消费体验，不会改变包真实导出。
