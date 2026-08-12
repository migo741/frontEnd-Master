# 第 07 章参考答案

## 练习一：用 composition root 消除初始化环

原图是 `registry -> csv -> registry`。求值 `registry.js` 时先求值 `csv.js`；后者在初始化自身导出后执行 `registry.set`，但 `registry` 的 `const` 初始化尚未发生，因此读取处于暂时性死区的绑定，抛出 `ReferenceError`。不同转译产物可能表现不同，但都不该依赖这个顺序。

参考拆分：

```js
// registry.js
export function createRegistry() {
  const plugins = new Map()

  return Object.freeze({
    register(plugin) {
      if (!plugin || typeof plugin.name !== 'string' || typeof plugin.parse !== 'function') {
        throw new TypeError('Invalid plugin contract')
      }
      if (plugins.has(plugin.name)) {
        throw new Error('Duplicate plugin: ' + plugin.name)
      }
      plugins.set(plugin.name, plugin)
    },
    require(name) {
      const plugin = plugins.get(name)
      if (!plugin) throw new Error('Missing plugin: ' + name)
      return plugin
    },
    names() {
      return [...plugins.keys()]
    },
  })
}

// csv.js
export const csvPlugin = Object.freeze({
  name: 'csv',
  parse(text) {
    return text.split(/\r?\n/).map(line => line.split(','))
  },
})

// bootstrap.js
import {createRegistry} from './registry.js'
import {csvPlugin} from './csv.js'

export function bootstrap() {
  const registry = createRegistry()
  registry.register(csvPlugin)
  return registry
}

// app.js
import {bootstrap} from './bootstrap.js'
const registry = bootstrap()
console.log(registry.require('csv').parse('a,b'))
```

测试核心：

```js
import assert from 'node:assert/strict'
import {createRegistry} from './registry.js'
import {csvPlugin} from './csv.js'

const registry = createRegistry()
registry.register(csvPlugin)
assert.deepEqual(registry.names(), ['csv'])
assert.throws(() => registry.register(csvPlugin), /Duplicate plugin: csv/)
assert.throws(() => registry.require('json'), /Missing plugin: json/)

const one = await import('./csv.js')
const two = await import('./csv.js')
assert.equal(one, two)
assert.equal(one.csvPlugin, two.csvPlugin)
```

最后两个断言只证明相同解析 URL 的模块缓存。若导入 `./csv.js?x=1`，那是另一个身份，不能依靠缓存防重复业务注册。真正的防线仍是显式 registry 契约。

`setTimeout` 只是把危险读取移到另一个 task，依赖环和初始化所有权仍然存在；加载速度、测试时钟或失败重试一变，问题会回来。

## 练习二：先缩短关键链，再讨论切块数量

原始关键链可抽象为：

```text
HTML
 -> entry chunk
    -> config module evaluate
       -> config fetch
          -> router evaluate
             -> first render
                -> detail import
                   -> detail data fetch
```

图表库与双份 analytics 同时增加下载、解析和执行成本。优化目标不是 chunk 越多越好，而是首个可用界面所需链更短、低频代码不进入首屏、代码与数据能并行。

参考启动边界：

```js
// bootstrap.js
import {createApp} from './app-shell.js'
import {createAnalytics} from './analytics.js'

async function loadConfig(signal) {
  const response = await fetch('/api/config', {signal})
  if (!response.ok) throw new Error('Config HTTP ' + response.status)
  return response.json()
}

export async function bootstrap() {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort('config-timeout'), 1500)

  try {
    const config = await loadConfig(controller.signal).catch(error => {
      reportBootstrapError(error)
      return {flags: {}, mode: 'degraded'}
    })
    const analytics = createAnalytics(config)
    return createApp({config, analytics})
  } finally {
    clearTimeout(timer)
  }
}
```

路由匹配后可同时启动代码和数据：

```js
export async function openTicket(id, signal) {
  const modulePromise = import('./routes/ticket.js')
  const dataPromise = fetch('/api/tickets/' + encodeURIComponent(id), {signal})
  const [route, response] = await Promise.all([modulePromise, dataPromise])
  if (!response.ok) throw new Error('Ticket HTTP ' + response.status)
  return route.render(await response.json())
}
```

管理图表仅在服务端确认权限后的管理路由导入。前端隐藏路由只是体验，接口仍需校验 actor、tenant 与资源权限。

analytics 统一从一个公开说明符导入；工厂内部以一次实例拥有生命周期。若 HMR、微前端或 URL 变体不可避免，`init` 仍应检测重复 listener，并提供 `dispose`，而不是静默叠加。

合格证据至少包括：

- manifest 显示图表库不在首页静态依赖闭包；
- bundle visualizer 中 analytics 只有一个解析实例；
-冷缓存 waterfall 中配置之后不再串行等待详情代码再取数据；
- Performance 中首屏脚本 parse/evaluate 降低，主线程长任务有前后对比；
- chunk 加载失败可呈现恢复 UI，而非永久空白；
- 发布系统按版本保留旧 hash 资源，时间覆盖最长活跃会话或采用原子版本目录。

预算示例要绑定测试环境，例如：“中端移动设备、4G 模拟下，首屏自有 JS gzip 不超过 180 KiB；首个可交互视图前关键请求串行深度不超过 3；任何路由 chunk reject 都在 1 秒内显示可重试错误”。数值需由项目基线校准。

## 边界与复写任务

不要为了 visualizer 图好看把紧密协作的 2 KiB 模块切成十几个请求；也不要把所有 vendor 固定成一个永不失效的大包。缓存命中、变更频率、压缩和协议开销要一起测。

关闭答案后，从空目录复写 `registry.js`、`csv.js`、`bootstrap.js`，再故意用 query string 导入第二份插件，证明“模块缓存”和“业务幂等”是两道不同防线。
