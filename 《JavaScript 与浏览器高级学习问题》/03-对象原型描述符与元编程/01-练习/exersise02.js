// 契约：

// 1. 返回新对象，不修改 base 与 traits；结果原型与 base 相同。
// 2. 复制 base 与 trait 的全部自有键，包括 Symbol、不可枚举属性和访问器。
// 3. 组合期间不得执行 getter。
// 4. traits 之间出现重复键时报冲突；可通过 `resolve(key, descriptors)` 显式解决。
// 5. `constructor`、`prototype`、`__proto__` 默认拒绝，除非白名单允许。
// 6. 任何失败都不能留下半成品可观察状态。
// 7. 测试 getter 零执行、Symbol、descriptor 标记、冲突与带 `super` 方法的边界。

// 要求在答案中解释：为什么复制一个使用 `super` 的方法后，它不会改用 result 的原型作为 super。

const composeTraits = function (base, ...traits) {}
