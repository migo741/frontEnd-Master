# 第 09 章答案：让构建与包契约可以被证明

## 题 1 参考答案：一个最小但完整的虚拟模块插件

### 1. 运行时类型和校验

```ts
import { existsSync, readFileSync, statSync } from 'node:fs'
import { resolve } from 'node:path'
import type { ModuleNode, Plugin, ViteDevServer } from 'vite'

interface BuildInfo {
  readonly release: string
  readonly buildTime: string
  readonly channel: 'local' | 'staging' | 'production'
}

interface BuildInfoPluginOptions {
  release: string
  channel: BuildInfo['channel']
  metadataFile?: string
}

function assertShortText(name: string, value: unknown): string {
  if (typeof value !== 'string' || value.length === 0 || value.length > 80) {
    throw new Error(`${name} must be a non-empty string up to 80 chars`)
  }
  return value
}

function assertChannel(value: unknown): BuildInfo['channel'] {
  if (value === 'local' || value === 'staging' || value === 'production') return value
  throw new Error('invalid release channel')
}

function parseMetadata(text: string): Partial<Pick<BuildInfo, 'release' | 'channel'>> {
  if (text.length > 16 * 1024) throw new Error('metadata file exceeds 16KB')
  const value: unknown = JSON.parse(text)
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new Error('metadata must be an object')
  }

  const record = value as Record<string, unknown>
  const unknownKeys = Object.keys(record).filter(key => key !== 'release' && key !== 'channel')
  if (unknownKeys.length) throw new Error(`unknown metadata fields: ${unknownKeys.join(', ')}`)

  return {
    release: record.release === undefined
      ? undefined
      : assertShortText('release', record.release),
    channel: record.channel === undefined
      ? undefined
      : assertChannel(record.channel),
  }
}
```

这里对 `record` 的断言发生在已确认普通对象后，后续每个字段仍逐一验证；不是把外部 JSON 直接断言成 BuildInfo。

### 2. 插件实现

```ts
const publicId = 'virtual:build-info'
const resolvedId = '\0virtual:build-info'

export function buildInfoPlugin(options: BuildInfoPluginOptions): Plugin {
  const buildTime = new Date().toISOString() // 插件实例创建一次，整个构建稳定
  const metadataPath = options.metadataFile
    ? resolve(options.metadataFile)
    : null
  let server: ViteDevServer | null = null
  let warnedMissing = false

  function currentInfo(): BuildInfo {
    const defaults = {
      release: assertShortText('release', options.release),
      channel: assertChannel(options.channel),
    }

    if (!metadataPath || !existsSync(metadataPath)) {
      return { ...defaults, buildTime }
    }

    const stats = statSync(metadataPath)
    if (stats.size > 16 * 1024) throw new Error('metadata file exceeds 16KB')
    const override = parseMetadata(readFileSync(metadataPath, 'utf8'))
    return { ...defaults, ...override, buildTime }
  }

  function invalidateVirtualModule(): ModuleNode | null {
    const module = server?.moduleGraph.getModuleById(resolvedId) ?? null
    if (module) server?.moduleGraph.invalidateModule(module)
    return module
  }

  return {
    name: 'ops:build-info',

    configResolved() {
      // 让默认值在启动阶段就失败，不等页面第一次 import。
      assertShortText('release', options.release)
      assertChannel(options.channel)
    },

    configureServer(devServer) {
      server = devServer
      if (metadataPath) devServer.watcher.add(metadataPath)
    },

    resolveId(id) {
      return id === publicId ? resolvedId : null
    },

    load(id) {
      if (id !== resolvedId) return null

      if (metadataPath && !existsSync(metadataPath) && !warnedMissing) {
        warnedMissing = true
        this.warn(`build metadata missing: ${metadataPath}; using defaults`)
      }

      // JSON.stringify 同时处理引号、换行和 </script> 等 JS 字符串内容；
      // 这是 JS 模块而非内联 HTML，仍只允许已验证字段。
      return `export default Object.freeze(${JSON.stringify(currentInfo())});`
    },

    handleHotUpdate(context) {
      if (!metadataPath || resolve(context.file) !== metadataPath) return

      try {
        currentInfo() // 先验证；坏 JSON 不保留“看似成功”的更新
        const module = invalidateVirtualModule()
        if (module) return [module]
        context.server.ws.send({ type: 'full-reload' })
        return []
      } catch (error) {
        context.server.ws.send({
          type: 'error',
          err: {
            message: error instanceof Error ? error.message : 'invalid build metadata',
            stack: error instanceof Error ? error.stack : undefined,
          },
        })
        return []
      }
    },
  }
}
```

生产项目还应考虑文件原子替换事件是否触发 watcher，以及 Windows path 大小写/规范化。若 HMR 虚拟模块在目标 Vite 版本表现不稳定，明确采用 full reload 更可靠。

### 3. 类型声明

```ts
// src/types/virtual-build-info.d.ts
declare module 'virtual:build-info' {
  interface BuildInfo {
    readonly release: string
    readonly buildTime: string
    readonly channel: 'local' | 'staging' | 'production'
  }

  const buildInfo: Readonly<BuildInfo>
  export default buildInfo
}
```

确保该 `.d.ts` 被应用 tsconfig include。若插件发布为独立包，可在包内导出 types 并让消费者在 `types` 或 tsconfig 引入。

### 4. Hook 因果顺序

```text
create plugin（固定 buildTime）
  -> configResolved（校验默认配置）
  -> dev only configureServer（保存 server + watch file）
  -> consumer imports publicId
  -> resolveId(publicId) => \0resolvedId
  -> load(\0resolvedId) => generated ESM
  -> metadata changes
  -> handleHotUpdate -> validate -> invalidate virtual module -> HMR/full reload
```

### 5. 测试

```ts
it('只解析目标 public id', async () => {
  const plugin = buildInfoPlugin({ release: 'r1', channel: 'local' })
  expect(await callHook(plugin.resolveId, 'virtual:build-info')).toBe('\0virtual:build-info')
  expect(await callHook(plugin.resolveId, './normal.ts')).toBeNull()
})

it('恶意 release 只能成为字符串数据', async () => {
  const release = '\";globalThis.pwned=true;//\n'
  const plugin = buildInfoPlugin({ release, channel: 'local' })
  const source = await callLoad(plugin, '\0virtual:build-info')
  expect(source).toContain(JSON.stringify(release))
  expect(source).not.toContain('process.env')
})

it('同一插件实例多次 load 的 buildTime 相同')
it('未知字段/坏 JSON/超长字段使构建失败')
it('metadata 缺失使用默认并只 warn 一次')
it('Vite fixture build 后模块只含三字段')
it('dev 修改 metadata 后页面收到新 release')
```

集成测试应真正启动 Vite fixture 或调用 `vite.build`，因为手调 hook 不能发现插件顺序、虚拟 ID 编码和 HMR graph 问题。产物再做 secret canary 扫描：在 CI env 放一段专用假 secret，确认 bundle 中不存在。

### 6. 运行时配置替代方案

若使用 `/config.json`，同一镜像可跨环境，但增加：首屏请求/失败、缓存版本、运行时 schema、CSP `connect-src`、配置被篡改的威胁模型。若内联到 HTML，要用安全 JSON 序列化避免闭合 script。build info 通常与产物版本绑定，更适合编译期；API base 等可能适合运行时。

### 7. 错误方案

- `export default ${process.env}`：泄露且不能序列化控制。
- `export default { release: '${release}' }`：引号/换行可破坏模块源。
- `new Date()` 写在 `load`：同一构建多次加载值不同，破坏可复现性。
- metadata 损坏继续返回上次值且无错误：开发者误以为更新生效。

---

## 题 2 参考答案：以 tarball 消费结果定义“可发布”

### 1. 依赖方向

```text
admin-web
  -> ticket-feature
  -> ui

ticket-feature
  -> ticket-domain
  -> api-contract
  -> ui

ui -> Vue(peer) + tokens
api-contract -> runtime schema library
ticket-domain -> no Vue, no DOM, no app

禁止：domain -> feature/ui/app
禁止：ui -> feature/app
禁止：feature -> app
禁止：任意消费者 -> */src/internal
```

允许 feature 之间互相导入会快速形成环；跨 feature 能力应通过应用编排或提取共享领域契约，而不是深导内部 store。

### 2. `@ops/ui/package.json`

```json
{
  "name": "@ops/ui",
  "version": "0.1.0",
  "private": false,
  "type": "module",
  "files": ["dist", "README.md"],
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "import": "./dist/index.js"
    },
    "./tokens.css": "./dist/tokens.css"
  },
  "sideEffects": ["**/*.css"],
  "peerDependencies": {
    "vue": "^3.5.0"
  },
  "devDependencies": {
    "vue": "^3.5.0"
  }
}
```

没有导出 `./src/*`、`./internal/*` 或通配 subpath。`devDependencies` 让库自身可测试，`peerDependencies` 让消费者提供单一运行时。是否使用 `peerDependenciesMeta` optional 取决于库是否真的能无 Vue 工作，本例不能设 optional。

### 3. 公开入口

```ts
// src/index.ts
export { default as OpsButton } from './components/OpsButton.vue'
export { default as OpsDialog } from './components/OpsDialog.vue'
export type { OpsDialogProps, OpsDialogEmits } from './components/dialog.contract'

// 不导出 internal focus stack、DOM helpers 或私有 token。
```

CSS 入口由构建复制为 `dist/tokens.css`，消费者显式：

```ts
import '@ops/ui/tokens.css'
```

如果组件 CSS 自动注入，副作用和 SSR 更复杂；显式 CSS 入口契约更清楚。

### 4. Library build

```ts
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  build: {
    lib: {
      entry: fileURLToPath(new URL('./src/index.ts', import.meta.url)),
      formats: ['es'],
      fileName: () => 'index.js',
    },
    rollupOptions: {
      external: ['vue'],
      output: {
        preserveModules: false,
      },
    },
    sourcemap: true,
  },
})
```

类型可用 `vue-tsc` + declaration 工具/专门 d.ts bundler 生成。最终检查 `dist/index.d.ts` 不包含 `../src/internal`、monorepo 绝对路径或未导出私有类型。不同工具版本配置不同，锁定并用 consumer `tsc --noEmit` 验证结果，而不是相信“生成命令退出 0”。

### 5. 架构守卫

ESLint 概念配置：

```js
{
  files: ['packages/ui/**/*.{ts,vue}'],
  rules: {
    'no-restricted-imports': ['error', {
      patterns: ['@ops/*-feature/**', 'apps/**', '@ops/*/src/**']
    }]
  }
}
```

图工具再执行：

```text
rule 1 packages/ticket-domain mayNotDependOn [vue, browser builtins, features, apps]
rule 2 packages/ui mayNotDependOn [features, apps]
rule 3 packages/*-feature mayNotDependOn [apps, other feature internals]
rule 4 all packages forbidden circular dependencies
rule 5 consumers forbidden path matching /src/internal/
```

字符串 lint 处理明显路径，dependency graph 工具处理 alias、间接依赖和环。二者互补。

### 6. Tarball consumer fixture

CI 流程：

```text
build @ops/ui
  -> npm pack --json
  -> 创建干净 fixture（不继承根 tsconfig paths）
  -> 安装 tarball + Vue + Vite
  -> import @ops/ui and @ops/ui/tokens.css
  -> typecheck
  -> production build
  -> preview smoke：按钮存在且关键 token 生效
  -> 尝试 import @ops/ui/src/internal/modal -> 预期失败
  -> 分析产物只有一个 Vue runtime
```

fixture 的 package manager workspace 配置要避免自动软链回源码，否则又制造假阳性。可以在临时仓库/容器中只安装 tarball。

SSR 支持声明后增加：Node 环境 import 不访问 `window/document`、`renderToString` 成功、客户端 hydration 无 mismatch、CSS 收集策略明确。

### 7. 重复 Vue 与 CSS 测试

- 构建库后搜索产物，不应包含 Vue runtime 标志性大段代码；
- 应用依赖图 `why/list vue` 只解析兼容单版本；
- bundle analyzer 看 Vue 一份；
- fixture mount 组件，provide/inject 跨 app/library 正常；
- 引入 tokens.css 后 computed style/visual snapshot 命中预期变量；
- 不引 CSS 时按契约明确失败或无主题，不能偶发由 monorepo 全局 CSS 掩盖。

### 8. CI 与缓存输入

```text
影响 @ops/ui build/test 的输入：
  packages/ui/src/**
  packages/ui/package.json
  root/package lockfile
  shared tsconfig + ui tsconfig
  vite/type generation config
  Node + package manager version
  直接内部依赖的公开产物/hash
  allowlisted PUBLIC build env
```

codegen：从 schema 生成后执行版本控制 diff，漂移即失败。普通按钮改动应只触发 UI 及其下游应用任务，不触发无依赖的 backend 包；任务图根据 package dependency 计算 affected，而非“仓库任一文件变就全跑”。

缓存中不放未声明网络结果；secret 不写入 key/log/产物。lockfile 变化至少使依赖安装和受影响构建失效。

### 9. Chunk 与预算

UI 库本身保持 ESM tree-shakeable；最终 chunk 决策主要由应用做。为 fixture 建预算：

- 只引 Button 时不应打入 Dialog/大型依赖；
- Vue external；
- CSS 体积上限；
- gzip/brotli 后 JS 与主线程执行对比基线。

不要只以文件个数验收；动态 import 的 waterfall 与实际路由交互也要跑。

### 10. 源码或 dist 的选择

本答案把 dist/tarball 视为正式契约，开发可用 package watch 提升反馈。优点是本地和外部消费者一致；代价是 watch/build 编排更复杂。如果选择源码消费，就必须让所有应用工具链兼容，并另外跑 dist consumer fixture保证发布。最危险的是 tsconfig path 默默绕过 exports，且 CI 从不安装产物。

### 11. 错误方案

- 只在 README 写“不要深导”：没有执行力。
- Vue 只设 peer，不在 bundler external：仍可能打进产物。
- `sideEffects:false` 后发现 CSS 丢失再让应用碰巧全局引入：契约不稳定。
- fixture 位于 workspace 且继承 paths：测试的是源码，不是 tarball。
- 一个巨型 root barrel 导出所有包：边界和 tree shaking都恶化。

### 复建要求

关掉答案后，独立写出四样东西：

1. 五层依赖方向图；
2. 最小 `exports/peerDependencies/sideEffects`；
3. tarball consumer 流程；
4. 影响缓存 key 的输入集合。

若只能写 Vite config 而无法证明消费者行为，还未达到“工程化完成”。
