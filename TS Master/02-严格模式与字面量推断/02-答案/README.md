# 第 02 章参考答案

## 练习一

```ts
type Feature = 'home' | 'billing' | 'admin'

type PublicRoute = {path: `/${string}`; roles?: never}
type ProtectedRoute = {
  path: `/${string}`
  roles: readonly [string, ...string[]]
}

type RouteConfig = {
  home: PublicRoute
  billing: ProtectedRoute
  admin: ProtectedRoute
}

const routes = {
  home: {path: '/'},
  billing: {path: '/billing', roles: ['member']},
  admin: {path: '/admin', roles: ['admin']},
} as const satisfies RouteConfig

function getPath<K extends keyof typeof routes>(feature: K): (typeof routes)[K]['path'] {
  return routes[feature].path
}
```

`satisfies RouteConfig` 已检查精确 keys（对象字面量上下文），`as const` 保留嵌套字面量/readonly tuple。显式 `: RouteConfig` 的读取通常只有 `/${string}`；单独 `as const` 不验证覆盖/业务约束；`as RouteConfig` 可能跳过错误并丢精确类型。

若需要安全遍历，封装一次：

```ts
function typedKeys<const T extends object>(value: T): Array<keyof T> {
  return Object.keys(value) as Array<keyof T>
}
```

这里断言建立在 Object.keys 返回自有可枚举字符串键、对象未在运行时增加隐藏键的局部契约。边界 helper 有测试，业务不重复断言。若 symbol/number key 或不可信对象，契约不成立。

## 练习二

推荐按项目/目录试点而非 flags 横扫：先建立 `noEmit` 基线和错误分类；拆环境 config/显式 types；开启 strict 核心中的 noImplicitAny/useUnknownInCatch/strictNullChecks，再索引安全与 exact optional。每阶段新/改文件必须零新增，存量以生成的 allowlist/baseline 阻断反弹。

Patch 三态应建模：

```ts
type FieldPatch<T> =
  | {kind: 'unchanged'}
  | {kind: 'set'; value: T}
  | {kind: 'clear'}
```

或按 API 约定使用 `null` 清除、缺失不改，Schema 明确。机械 `| undefined` 继续混淆 JSON（undefined 会消失）和对象 spread。

codemod 适合插入 `override`、拆 type-only import、生成 config references、把明显 catch error 改 unknown+helper；无法自动决定业务 null/undefined、字典是否全键、断言是否真实。指标：生产 null/index 错误、边界 Schema 覆盖、IDE p95、typecheck 时长、suppression/any 预算、受影响 PR lead time。试点先选边界清晰且有测试的 feature，灰度 CI 后扩散。

