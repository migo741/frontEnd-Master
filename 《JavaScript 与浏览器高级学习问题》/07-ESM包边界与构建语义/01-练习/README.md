# 第 07 章练习

## 练习一：拆掉会白屏的插件初始化环

给定三个原生 ESM 文件：

```js
// registry.js
import {csvPlugin} from './csv.js'
export const registry = new Map([['default', csvPlugin]])

// csv.js
import {registry} from './registry.js'
export const csvPlugin = {name: 'csv', parse: text => text.split('\n')}
registry.set(csvPlugin.name, csvPlugin)

// app.js
import {registry} from './registry.js'
console.log(registry)
```

任务：

1. 不运行先画模块图和求值顺序，指出哪次顶层读取可能触发 `ReferenceError`。
2. 重构为 `registry.js`、`csv.js` 都没有互相依赖，由 `bootstrap.js` 显式注册。
3. 注册必须拒绝重复名字，且重复导入同一 canonical URL 不会重复初始化。
4. 写浏览器测试或 Node ESM 测试，覆盖正常注册、重复注册和缺失插件。
5. 用一句话解释为什么把注册推迟到 `setTimeout` 不是修复。

验收：依赖图无环；导入模块本身不改全局注册表；错误包含冲突插件名；测试不依赖文件恰好按某个顺序执行。

## 练习二：首屏 chunk 瀑布法医（高难）

一个后台系统出现以下现象：

- 首页入口静态导入管理端图表库，普通用户也下载；
- `config.js` 用 top-level await 请求租户配置，路由代码必须等它；
- 首页渲染后才动态导入详情页，详情页求值后才请求数据；
- analytics 分别通过 `./analytics.js` 与带 query 的 URL 导入，页面产生两次初始化；
- 开发环境很快，生产弱网白屏 4 秒。

在任意现代 bundler 建一个最小复现并完成：

1. 画“代码、配置、数据”三条加载链，标出可并行点。
2. 把管理端能力移到权限通过后的路由边界，但不能只靠前端权限保护数据。
3. 把配置启动改成显式、可超时、可降级的 bootstrap；详情代码和数据尽可能并行预取。
4. 统一 analytics 的模块身份，并让初始化幂等。
5. 保存 production build manifest、bundle 图、冷缓存 Network waterfall 与一次 Performance 记录。
6. 定义首屏 JS、请求串行深度和失败 chunk 的预算，并说明滚动发布如何保留旧资源。

不接受“加一个 `manualChunks` 就完成”。答案必须解释边界、失败恢复和前后证据。

## 复盘交付

用不超过 250 字回答：源码模块边界、构建 chunk 边界和产品功能边界为什么不必一一对应？
