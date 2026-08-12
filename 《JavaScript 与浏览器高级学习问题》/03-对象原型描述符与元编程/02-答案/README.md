# 第 03 章答案

## 练习 1：构造与实例判断

### 因果链

new 先决定实例原型，再用实例作为 this 调用函数，最后应用“对象返回值优先”规则。

instanceof 的普通部分则反向沿 value 的原型链查找 Constructor.prototype。

箭头函数不可构造；仅检查 typeof function 不足以完整判断 constructability。

### 可复制实现

```js
function assertConstructable(value) {
  if (typeof value !== "function") {
    throw new TypeError("Constructor must be callable");
  }
  // 把 value 只放在 newTarget 位置：执行的是空函数，不会执行 value 的函数体。
  // Reflect.construct 会先对 newTarget 做规范内部的 IsConstructor 检查。
  Reflect.construct(function ProbeTarget() {}, [], value);
}

export function construct(Constructor, ...args) {
  assertConstructable(Constructor);
  const prototype =
    (typeof Constructor.prototype === "object" && Constructor.prototype !== null)
      ? Constructor.prototype
      : Object.prototype;
  const instance = Object.create(prototype);
  const returned = Reflect.apply(Constructor, instance, args);
  const isObject = returned !== null &&
    (typeof returned === "object" || typeof returned === "function");
  return isObject ? returned : instance;
}

const defaultHasInstance = Object.getOwnPropertyDescriptor(
  Function.prototype,
  Symbol.hasInstance,
).value;

function findEffectiveHasInstanceDescriptor(Constructor) {
  for (let owner = Constructor; owner !== null; owner = Reflect.getPrototypeOf(owner)) {
    const descriptor = Reflect.getOwnPropertyDescriptor(owner, Symbol.hasInstance);
    if (descriptor) return {owner, descriptor};
  }
  return null;
}

export function ordinaryInstanceOf(value, Constructor) {
  if (typeof Constructor !== "function") throw new TypeError("Right side is not callable");
  const effective = findEffectiveHasInstanceDescriptor(Constructor);
  const usesDefault =
    effective === null ||
    (effective.owner === Function.prototype &&
      "value" in effective.descriptor &&
      effective.descriptor.value === defaultHasInstance);
  if (!usesDefault) {
    throw new TypeError("Custom Symbol.hasInstance is outside this exercise");
  }
  if (value === null || (typeof value !== "object" && typeof value !== "function")) {
    return false;
  }
  const prototype = Constructor.prototype;
  if ((typeof prototype !== "object" && typeof prototype !== "function") || prototype === null) {
    throw new TypeError("Constructor has non-object prototype");
  }
  for (let cursor = Object.getPrototypeOf(value); cursor !== null;
       cursor = Object.getPrototypeOf(cursor)) {
    if (cursor === prototype) return true;
  }
  return false;
}
```

### 测试与边界

测试普通构造器、返回 `{}`、返回函数、返回 `1`、后改 prototype 的构造器。

箭头函数与 generator function 虽然 `typeof` 都是 `"function"`，却没有 `[[Construct]]`；预检必须像原生 new 一样抛 TypeError。

```js
let arrowCalls = 0;
const arrow = () => { arrowCalls += 1; };
assert.throws(() => construct(arrow), TypeError);
assert.equal(arrowCalls, 0); // 探测没有执行目标函数体
assert.throws(() => construct(function* generator() {}), TypeError);

function Plain() {}
assert.equal(ordinaryInstanceOf(Object.create(Plain.prototype), Plain), true);

function CustomParent() {}
Object.defineProperty(CustomParent, Symbol.hasInstance, {
  value() { return true; },
});
function InheritsCustom() {}
Object.setPrototypeOf(InheritsCustom, CustomParent);
assert.throws(
  () => ordinaryInstanceOf({}, InheritsCustom),
  /Custom Symbol\.hasInstance/,
);

let getterCalls = 0;
const customCarrier = Object.create(Function.prototype);
Object.defineProperty(customCarrier, Symbol.hasInstance, {
  get() {
    getterCalls += 1;
    return () => true;
  },
});
function InheritsGetter() {}
Object.setPrototypeOf(InheritsGetter, customCarrier);
assert.throws(() => ordinaryInstanceOf({}, InheritsGetter), TypeError);
assert.equal(getterCalls, 0); // descriptor walk 不执行自定义 getter
```

它不支持 class，因为 class 不能通过普通 Reflect.apply 调用。

它也不能正确传递 `new.target`，不能安全构造 Array、Map 等内建派生类型。

生产代码使用 `Reflect.construct(Constructor, args, NewTarget)`。

原生 instanceof 会先解析包括继承属性在内的 `Symbol.hasInstance`。参考函数沿构造器原型链找第一个 descriptor：没有 handler，或命中 `Function.prototype` 上的标准默认方法才进入 ordinary 算法；任何自有/继承的自定义 value 或 getter 都拒绝，且检查过程不会执行 getter。

### 复写任务

合上答案重写，再只用 `Reflect.construct` 实现支持独立 NewTarget 的版本，并为两者建立差异测试。

## 练习 2：trait 组合器

### 因果链

读取 descriptor 而不是属性值，才能避免 getter 执行并保留属性协议。

先把全部输入变成一份“计划”，完成冲突与安全检查，再创建结果，可保证失败不泄露半成品。

结果是新对象，因此无需在原 base 上实现不可行的事务回滚。

### 可复制实现

```js
const blocked = new Set(["constructor", "prototype", "__proto__"]);
const TRAIT_OPTIONS = Symbol("traitOptions");

export function composeTraits(base, ...rest) {
  if (base === null || (typeof base !== "object" && typeof base !== "function")) {
    throw new TypeError("base must be an object");
  }

  let options = {};
  const candidate = rest.at(-1);
  if (candidate !== null &&
      (typeof candidate === "object" || typeof candidate === "function")) {
    // 只读取 Symbol 对应的 descriptor，不读取 candidate.__traitOptions，
    // 因此普通对象上的同名 getter 不会在“是否为 options”检测阶段执行。
    const marker = Object.getOwnPropertyDescriptor(candidate, TRAIT_OPTIONS);
    if (marker && "value" in marker && marker.value === true) options = rest.pop();
  }
  const allow = new Set(options.allow ?? []);
  const resolve = options.resolve;
  const plan = new Map();

  function safeKey(key) {
    if (typeof key === "string" && blocked.has(key) && !allow.has(key)) {
      throw new TypeError(`Blocked trait key: ${key}`);
    }
  }

  for (const key of Reflect.ownKeys(base)) {
    safeKey(key);
    plan.set(key, [Object.getOwnPropertyDescriptor(base, key)]);
  }

  for (const trait of rest) {
    if (trait === null || (typeof trait !== "object" && typeof trait !== "function")) {
      throw new TypeError("trait must be an object");
    }
    for (const key of Reflect.ownKeys(trait)) {
      safeKey(key);
      const descriptor = Object.getOwnPropertyDescriptor(trait, key);
      const existing = plan.get(key);
      if (existing) existing.push(descriptor);
      else plan.set(key, [descriptor]);
    }
  }

  const finalDescriptors = new Map();
  for (const [key, descriptors] of plan) {
    if (descriptors.length === 1) {
      finalDescriptors.set(key, descriptors[0]);
      continue;
    }
    if (typeof resolve !== "function") {
      throw new TypeError(`Trait conflict at ${String(key)}`);
    }
    const selected = resolve(key, descriptors.map((item) => ({ ...item })));
    if (!selected || typeof selected !== "object") {
      throw new TypeError(`Resolver did not return descriptor for ${String(key)}`);
    }
    finalDescriptors.set(key, selected);
  }

  const result = Object.create(Object.getPrototypeOf(base));
  for (const [key, descriptor] of finalDescriptors) {
    Object.defineProperty(result, key, descriptor);
  }
  return result;
}

export function traitOptions(options = {}) {
  const normalized = {
    allow: options.allow === undefined ? [] : [...options.allow],
    resolve: options.resolve,
  };
  Object.defineProperty(normalized, TRAIT_OPTIONS, {
    value: true,
    enumerable: false,
    writable: false,
    configurable: false,
  });
  return Object.freeze(normalized);
}
```

调用示例：

```js
const merged = composeTraits(base, selectable, searchable, traitOptions({
  resolve(key, descriptors) {
    if (key !== "label") throw new Error(`Unexpected conflict: ${String(key)}`);
    return descriptors.at(-1);
  },
}));
```

### 测试要点

定义一个会递增计数器的 getter，组合后计数仍为零，读取结果属性后才变为一。

再把该 getter 命名为 `__traitOptions` 并把对象放在最后一项；检测过程仍不得执行它，也不得把它误认成 options。

用 `Object.getOwnPropertyDescriptor` 断言 writable/enumerable/configurable 与源一致。

用 Symbol 键验证 `Reflect.ownKeys` 没有遗漏。

重复键在 resolver 缺失时应于结果创建前抛错。

带 `super` 的方法复制后仍以“最初定义该方法的对象”为 `[[HomeObject]]`。

这是函数对象的内部语义，`defineProperty` 不会重写它；若 trait 需要动态 super，应改用显式委托或函数工厂。

### 边界与复写任务

示例通过模块私有 Symbol 的 descriptor 识别 options；普通字符串键无法伪装，检测也不会执行业务 getter。

若输入本身是 Proxy，`getOwnPropertyDescriptor` trap 仍可能执行；完全不信任的输入应改用固定参数位置和边界校验。

合上答案重写，再增加冲突策略 `chain`：多个普通函数按顺序调用，但任一函数抛错时立即停止。
