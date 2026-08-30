# 答案与复盘

## 题 1

```ts
export function buildInfoPlugin(info: BuildInfo): Plugin {
  const publicId = 'virtual:build-info'
  const internalId = '\0' + publicId
  return {
    name: 'build-info',
    resolveId(id) { if (id === publicId) return internalId },
    load(id) {
      if (id !== internalId) return
      return `export default ${JSON.stringify({
        commit: info.commit,
        buildTime: info.buildTime,
        appVersion: info.appVersion,
      })}`
    }
  }
}
```

私钥、token、内部服务凭证和个人信息绝不能进入模块；源代码和 sourcemap 都可能暴露它。测试调用插件 hooks，断言 public id 解析、其他 id 返回 undefined、输出可 import 且只有白名单；再做一次 integration build。buildTime 每次变化会破坏可复现构建，若无业务必要可改为发布版本和 commit。

## 题 2

允许方向示例：`app -> pages -> features -> entities -> shared`，同层 feature 之间不得深层互引；交互通过上层编排或公开事件/contract。每个模块只有 `index.ts` public API，package exports 或 ESLint `no-restricted-imports/boundaries` 阻止 `/internal/`。

迁移：先只记录违规和生成依赖图；选择变更频繁的一个 feature 建 public API；把真正共享的契约上移、实现保留原处；为新代码把规则设 error，旧违规白名单逐项消减；CI 展示违规趋势；最后关闭白名单。不要把所有 internal 一股脑 export，那只是把问题合法化。

