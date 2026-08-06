# 第 13 章参考答案

## 练习一

公共配置只放严格规则：

```json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "verbatimModuleSyntax": true,
    "skipLibCheck": false
  }
}
```

web 使用 `module: "ESNext"`、`moduleResolution: "Bundler"`、`noEmit: true`、DOM libs，不包含 node/vitest types。CLI 使用 TS 6 的 `module: "node20"`、对应 Node types、`outDir/rootDir`，源码相对 import 写 `./config.js`；跨 package 使用真实 workspace package 名和 exports。test 配置包含 `vitest/globals`（更推荐显式 import 测试 API），并只 include tests。

若保留 `@/*`，Vite 也要配置 alias；CLI 不使用它，或改为 package `imports` 的 `#...` 映射并让 Node/TS 同时理解。`paths` 不改输出 specifier，因此 Node 不认识 `@`。

验证清单：四份 `--showConfig`；分别 `tsc -p`；web build；CLI build 后真实 Node 运行；test；检查 dist import；`--traceResolution` 抽查；验证 web 中 `process` 报错；验证生产源码中 test global 报错；从 clean install 运行；CI 在支持的最低 Node 版本运行。

## 练习二

最稳妥方案是单一 ESM 核心，CJS wrapper 不能同步 require ESM 时要么提供异步入口，要么由构建生成 CJS，但共享状态放进 `globalThis` 上的 `Symbol.for('@acme/session.registry')`。不过 class constructor identity 仍可能分裂；不要跨格式依赖 `instanceof`，改用 brand/protocol guard，或确保整个进程只解析到一种格式。

exports 明确 `.` 和 `./testing` 的 types/import/require，package files 白名单只发布 dist/package metadata。不要导出 `./*`，这样 internal deep import 会失败。

consumer fixtures 必须安装打包后的 `.tgz`，不能直接引用 src：

- ESM Node：`import`、子路径、错误深引入。
- CJS Node：`require`、相同功能。
- Vite：production build + browser smoke。

如果维护成本超过真实 CJS 用户价值，或 API 天然异步、生态最低 Node 已支持 ESM，优先 ESM-only，并通过 major version 清晰迁移。双格式不是高级标志，而是两套协议的长期兼容承诺。
