// ## 练习一：类型安全配置注册表

// 构建路由配置：

// ```ts
// type Feature = 'home' | 'billing' | 'admin'
// ```
// 要求：

// - 配置必须恰好覆盖所有 Feature；每个 path 是 `/${string}`。
// - `admin` 的具体 path 能推断为 `'/admin'`，不能被拓宽成 string。
// - `roles` 若存在必须为非空 readonly 数组；home 禁止 roles。
// - `getPath('billing')` 返回对应字面量；错误 feature 编译失败。
// - 禁止 `as RouteConfig` 和 non-null assertion。
// - 运行时 `Object.keys` 的 string[] 边界要局部安全处理。

// 比较三版：显式注解、`as const`、`as const satisfies`；解释调用端差异。

type Feature = "home" | "billing" | "admin";
type RouteFeature = {
  path: `/${string}`;
  roles?: readonly [string, ...string[]];
};
type PublicRoute = {
  path: `/${string}`;
};
type ConfigFeature = {
  home: PublicRoute;
  billing: RouteFeature;
  admin: RouteFeature;
};

const routeConfig = {
  home: { path: "/home" },
  billing: { path: "/billing", roles: ["member"] },
  admin: { path: "/admin", roles: ["admin"] },
} satisfies ConfigFeature;
type a = typeof routeConfig;
routeConfig.admin.roles = ["zs"];
console.log(routeConfig.admin.roles);
