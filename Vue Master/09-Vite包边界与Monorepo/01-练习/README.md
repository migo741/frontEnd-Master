# 第 09 章练习：Vite 插件与可执行包边界

> 两题分别训练 Vite 生命周期和 Monorepo 发布真实性。配置不是截图作业：必须有 fixture、失败测试和产物证据。

## 题 1：构建安全的 `virtual:build-info` 插件（机制题）

### 背景

应用需要在“关于”页和错误报告中展示：`release`、`buildTime`、`channel`。这些值来自 CI。开发模式修改一个受控 JSON 文件时应触发 HMR。过去有人把整个 `process.env` 暴露到虚拟模块，造成凭证泄漏。

### 契约

实现 Vite 插件：

```ts
function buildInfoPlugin(options: {
  release: string
  channel: 'local' | 'staging' | 'production'
  metadataFile?: string
}): Plugin
```

消费者：

```ts
import buildInfo from 'virtual:build-info'
```

同时提供 `.d.ts` 类型。插件必须：

1. 使用公开 ID 与 `\0` resolved ID；
2. `resolveId/load` 只处理目标模块；
3. 用安全序列化生成 ESM，不拼未经转义的字符串；
4. 只暴露三个白名单字段，不导出 env/commit message；
5. buildTime 在一次构建中稳定，不能每次 load 改变；
6. metadataFile 变化时只让虚拟模块失效并 HMR/全刷二选一；
7. 正确处理文件不存在、JSON 损坏和超长字段；
8. 插件在 build 与 serve 都可用；
9. 写出 hook 调用顺序说明。

### 规模与限制

- release 最长 80 字符、channel 枚举固定；
- metadata 文件最大 16KB，只允许覆盖 release/channel；
- 插件不得发网络请求；
- 不读取未声明 env；
- source map 问题可说明，不要求转换普通模块；
- 使用 Vitest 调用 hook 或 Vite fixture integration test。

### 失败语义

- JSON 损坏：dev 明确报错，build 失败；
- metadata file 不存在：使用 options 默认值并记录一次 warning；
- 字段不合法：构建失败，不输出部分脏模块；
- HMR 更新失败：允许 full reload，但不能悄悄保留错误旧值。

### 验收

- [ ] 虚拟 ID 协议正确；
- [ ] 字符串含引号/换行也不会注入新 JS；
- [ ] buildTime 同构建多次 load 相同；
- [ ] 没有 secret/env 展开；
- [ ] `.d.ts` 让默认导入获得只读类型；
- [ ] dev HMR 与 build 各有一个 fixture 测试；
- [ ] 构建产物可搜索确认只含白名单；
- [ ] 解释 `configResolved/configureServer/handleHotUpdate` 的职责。

### 发散

- 若改成运行时 `/config.json`，部署灵活性、首屏失败模型和 CSP 有何变化？
- build info 是否应该影响所有 chunk hash？怎样减少不必要缓存失效？

---

## 题 2：把 `@ops/ui` 做成真正可发布的包（生产开放题）

### 背景

Monorepo 有：

```text
apps/admin-web
packages/ui
packages/ticket-feature
packages/ticket-domain
packages/api-contract
```

当前问题：应用深导 `@ops/ui/src/internal/modal.ts`；UI 包把 Vue 打进产物；CSS 被 tree-shake；feature 反向导入 app store；tsconfig paths 指向源码，导致 npm tarball 缺文件仍未被 CI 发现。

### 契约

重构并交付：

1. 依赖方向图与允许/禁止矩阵；
2. `@ops/ui/package.json` 的 `exports/files/peerDependencies/sideEffects`；
3. Vite library mode 配置，Vue external；
4. 根入口与允许的 CSS/subpath 入口；
5. 生成/打包 `.d.ts`，不泄漏 `src/internal` 类型；
6. ESLint 或 dependency-cruiser 架构守卫；
7. 从 `npm pack` tarball 安装的 consumer fixture；
8. 重复 Vue 检测；
9. bundle budget 和可视化检查；
10. CI/cache 输入清单。

### 规模与限制

- `@ops/ui` 30 个组件，目标 ESM-only；
- Vue `^3.5.0` 由消费者提供；
- CSS 必须显式入口，不能因 tree shaking 丢失；
- 不允许消费者访问 `src/internal`；
- `ticket-domain` 必须保持无 Vue/浏览器依赖；
- `ticket-feature` 可依赖 domain、api-contract、ui，不能依赖 app；
- 一次普通按钮改动不应让所有应用重新执行无关后端任务。

### 失败语义

- peer 缺失/版本不兼容：安装或启动阶段明确失败；
- consumer 深导内部路径：typecheck/build 失败；
- CSS 入口缺失：fixture visual/DOM style smoke 失败；
- 打入第二份 Vue：bundle/依赖图检查失败；
- codegen 输出与 schema 漂移：CI 失败；
- lockfile 变化：相关缓存必须失效。

### 验收

- [ ] package exports 是唯一公开面；
- [ ] tarball fixture 不依赖 monorepo paths 假象；
- [ ] Vue 同时在 peerDependencies 与 build external；
- [ ] CSS sideEffects 有消费测试；
- [ ] 至少 4 条依赖方向规则由 CI 执行；
- [ ] 解释源码消费与 dist 消费的选择；
- [ ] 解释 chunk 策略如何用数据验证；
- [ ] 列出最小、完整且不泄密的缓存 key 输入。

### 发散

- 组件要支持 SSR 时，consumer fixture 还应增加哪些测试？
- 如果未来同时支持 Vue 3.5 和 3.6，peer range、CI matrix 和条件特性如何设计？
