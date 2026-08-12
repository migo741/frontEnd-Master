# 第 03 章练习

本章只做两题；目标是把“看起来像对象”的直觉升级为可验证的对象协议。

## 练习 1（经典必做）：手写构造与实例判断

实现：

```js
function construct(Constructor, ...args) {}
function ordinaryInstanceOf(value, Constructor) {}
```

要求：

1. `construct` 实现普通用户函数的 new 四步语义。
2. 构造器返回对象/函数时采用其返回值，返回原始值时仍返回新实例。
3. prototype 不是对象时，按普通构造语义回退到 `Object.prototype`。
4. `ordinaryInstanceOf` 沿原型链判断，但必须明确拒绝 `Symbol.hasInstance` 自定义语义。
5. 测试 null、箭头函数、被修改的 prototype、返回函数的构造器。

最后写出为什么这两个实现不能完全替代 `Reflect.construct` 和原生 `instanceof`。

## 练习 2（高难）：descriptor-aware trait 组合器

实现：

```js
const result = composeTraits(base, ...traits);
```

契约：

1. 返回新对象，不修改 base 与 traits；结果原型与 base 相同。
2. 复制 base 与 trait 的全部自有键，包括 Symbol、不可枚举属性和访问器。
3. 组合期间不得执行 getter。
4. traits 之间出现重复键时报冲突；可通过 `resolve(key, descriptors)` 显式解决。
5. `constructor`、`prototype`、`__proto__` 默认拒绝，除非白名单允许。
6. 任何失败都不能留下半成品可观察状态。
7. 测试 getter 零执行、Symbol、descriptor 标记、冲突与带 `super` 方法的边界。

要求在答案中解释：为什么复制一个使用 `super` 的方法后，它不会改用 result 的原型作为 super。
