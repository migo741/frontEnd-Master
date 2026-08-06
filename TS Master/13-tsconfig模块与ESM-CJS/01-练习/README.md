# 第 13 章练习

## 练习一：修复“编辑器正常，运行失败”

仓库包含三个入口：

- `apps/web`：Vite 浏览器应用；
- `apps/cli`：Node 20 直接执行编译产物；
- `tests`：Vitest。

当前只有一个配置：

```json
{
  "compilerOptions": {
    "target": "ESNext",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "paths": { "@/*": ["src/*"] },
    "types": ["node", "vitest/globals"]
  }
}
```

CLI 中 `import '@/config'` 编译通过但 Node 报 `ERR_MODULE_NOT_FOUND`，浏览器源码可误用 `process`，测试 globals 泄漏到生产文件。

要求：

- 设计 base/web/cli/test 四份配置，说明每个关键选项归属。
- CLI 使用原生 Node ESM，不加自定义 loader。
- 解释相对 import 为什么写 `.js`，以及 paths 为什么不能解决 runtime。
- 给出至少 8 条验证命令或验证点。

## 练习二：双格式库的模块陷阱（高难）

设计 `@acme/session`，既支持 Node ESM import，也支持旧 CJS require，并提供 `./testing` 子路径。库内有一个 session registry singleton 和一个 `Session` class。

要求：

- 设计 package exports、输出布局和声明文件映射。
- 防止 ESM/CJS 两套实现产生两份 singleton/class identity。
- 禁止消费者访问 `dist/internal/*`。
- 建立 ESM、CJS、bundler 三种 consumer fixture。
- 分析哪些情况下你会放弃双格式，只发 ESM。
