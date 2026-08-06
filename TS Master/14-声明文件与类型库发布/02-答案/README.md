# 第 14 章参考答案

## 练习一

将 runtime build 和 declaration build 分开，入口源文件只 re-export 公共 API；AST 放 internal 且不从可达公共签名泄漏。`Infer<S>` 可用受约束条件类型读取私有 symbol brand，但对外错误类型保持命名、限制 union/递归规模。

exports 为 `.` 与 `./json` 分别配置 `types/import/require`，类型文件放与 runtime 入口对应的位置。CI 先 build、`npm pack`，再将 tgz 安装到四类空白 fixture；禁止 workspace symlink 替代打包物。正向用 `expectTypeOf`/assignability，负向用 `@ts-expect-error`，runtime 测每种 codec 的成功和失败。

典型 major 类型变更：提高最低 TS 版本；给公开结果 union 加成员；改变 Infer 推断；收窄 codec 输入；移除子路径；更换 ESM/CJS 声明形态。即便其中某些是 bugfix，也应先跑下游 fixture 和 API diff 决定版本。

## 练习二

CommonJS callable object 可用 function declaration + namespace merging，再 `export = createClient`：

```ts
declare function createClient(options?: createClient.Options): createClient.Client
declare namespace createClient {
  interface Options { timeout?: number }
  const defaults: Required<Options>
  class Client { use<P>(plugin: Plugin<P>): Client & P }
  interface Plugin<P> { install(client: Client): P }
}
export = createClient
```

真正实现若 `use` 返回原 client 且插件 mutation 它，声明可把返回值表达为 intersection，但调用者必须使用返回值：

```ts
const cached = client.use(cachePlugin)
cached.cache.get('x')
// @ts-expect-error plugin 未注册
client.cache
```

若项目要求 mutation 后原变量自动变窄，可设计 assertion method，但它有继承/显式 annotation 限制，API 也更隐晦；返回增强对象更清晰。runtime 测插件安装前属性不存在、安装后方法工作，且类型声明与真实 `use` 返回值一致。

`esModuleInterop` 可允许更自然的 default import emit/helper，却不会把 `module.exports = fn` 变成真实 ESM default export；发布者必须按真实 CJS 形态声明。
