# 第 01 章答案

## 练习 1：SameValue

### 因果链

`===` 已经覆盖绝大多数值，但有两个例外需要修正。

- 当 `a === b` 时，只有正负零需要继续区分；`1 / 0` 与 `1 / -0` 符号不同。
- 当 `a !== b` 时，只有 `NaN` 应被视为与自身相同；`NaN` 是唯一不等于自身的值。

### 可复制实现

```js
export function sameValue(a, b) {
  if (a === b) {
    return a !== 0 || 1 / a === 1 / b;
  }
  return a !== a && b !== b;
}
```

### 测试要点

```js
import assert from "node:assert/strict";
import { sameValue } from "./same-value.js";

const cases = [
  [1, 1], [1, "1"], [null, null], [null, undefined],
  [NaN, NaN], [0, -0], [-0, -0],
];

for (const [a, b] of cases) {
  assert.equal(sameValue(a, b), Object.is(a, b));
}

const object = {};
assert.equal(sameValue(object, object), true);
assert.equal(sameValue({}, {}), false);
```

| 算法 | `NaN` 与自身 | `0` 与 `-0` | 典型位置 |
|---|---:|---:|---|
| `===` | 否 | 是 | 普通比较、indexOf |
| SameValue | 是 | 否 | Object.is、部分状态比较 |
| SameValueZero | 是 | 是 | Map、Set、includes |

若状态容器使用 SameValue，重复写入 `NaN` 可跳过更新；从 `0` 写到 `-0` 会被视为变化。

### 边界与复写任务

Symbol、BigInt 和对象不需要特判，严格相等已经给出正确身份语义。

合上答案，改写 `sameValueZero`，并让测试对照 `new Set([a, b]).size`。

## 练习 2：无歧义 JSON 数据边界

### 设计决定

不能直接把特殊值替换为 `{ $type: "date" }`，因为用户数据可能长得一样。

参考协议把每一个值都编码成二元组：`[标签, 负载]`。

因此业务对象本身永远位于 `object` 标签的负载中，不会与协议标签冲突。

本题保留值结构，但不保留重复引用的身份；同一对象出现两次会编码两份。

循环引用拒绝，而不是引入对象 ID 协议。

### 可复制实现

```js
const own = Object.prototype.hasOwnProperty;

export function encode(input) {
  const ancestors = new Map();

  function visit(value, path) {
    if (value === undefined) return ["undefined"];
    if (typeof value === "number") {
      if (Number.isNaN(value)) return ["nan"];
      if (value === Infinity) return ["infinity"];
      if (value === -Infinity) return ["-infinity"];
      if (Object.is(value, -0)) return ["-0"];
      return ["number", value];
    }
    if (typeof value === "bigint") return ["bigint", value.toString()];
    if (value === null) return ["null"];
    if (["string", "boolean"].includes(typeof value)) {
      return [typeof value, value];
    }
    if (typeof value !== "object") {
      throw new TypeError(`Unsupported ${typeof value} at ${path}`);
    }
    if (ancestors.has(value)) {
      throw new TypeError(`Cycle at ${path}; ancestor is ${ancestors.get(value)}`);
    }

    ancestors.set(value, path);
    let encoded;
    if (value instanceof Date) {
      if (Number.isNaN(value.getTime())) throw new TypeError(`Invalid Date at ${path}`);
      encoded = ["date", value.toISOString()];
    } else if (Array.isArray(value)) {
      encoded = ["array", value.map((item, i) => visit(item, `${path}[${i}]`))];
    } else if (value instanceof Map) {
      encoded = ["map", [...value].map(([key, item], i) => [
        visit(key, `${path}.<key:${i}>`), visit(item, `${path}.<value:${i}>`),
      ])];
    } else if (value instanceof Set) {
      encoded = ["set", [...value].map((item, i) => visit(item, `${path}.<set:${i}>`))];
    } else if (Object.getPrototypeOf(value) === Object.prototype ||
               Object.getPrototypeOf(value) === null) {
      encoded = ["object", Object.keys(value).map((key) => [
        key, visit(value[key], `${path}.${key}`),
      ])];
    } else {
      throw new TypeError(`Unsupported object at ${path}`);
    }
    ancestors.delete(value);
    return encoded;
  }

  return JSON.stringify(visit(input, "$"));
}

export function decode(text) {
  const root = JSON.parse(text);

  function read(node) {
    if (!Array.isArray(node) || typeof node[0] !== "string") {
      throw new TypeError("Malformed tagged value");
    }
    const [tag, payload] = node;
    switch (tag) {
      case "undefined": return undefined;
      case "nan": return NaN;
      case "infinity": return Infinity;
      case "-infinity": return -Infinity;
      case "-0": return -0;
      case "null": return null;
      case "number":
        if (typeof payload !== "number" || !Number.isFinite(payload)) throw new TypeError("Bad number");
        return payload;
      case "string":
        if (typeof payload !== "string") throw new TypeError("Bad string");
        return payload;
      case "boolean":
        if (typeof payload !== "boolean") throw new TypeError("Bad boolean");
        return payload;
      case "bigint": return BigInt(payload);
      case "date": {
        const date = new Date(payload);
        if (Number.isNaN(date.getTime())) throw new TypeError("Bad date");
        return date;
      }
      case "array": return payload.map(read);
      case "map": return new Map(payload.map(([key, value]) => [read(key), read(value)]));
      case "set": return new Set(payload.map(read));
      case "object": {
        const result = Object.create(null);
        for (const pair of payload) {
          if (!Array.isArray(pair) || pair.length !== 2) throw new TypeError("Bad property");
          const [key, value] = pair;
          if (typeof key !== "string" || own.call(result, key)) throw new TypeError("Bad key");
          result[key] = read(value);
        }
        return result;
      }
      default: throw new TypeError(`Unknown tag: ${tag}`);
    }
  }
  return read(root);
}
```

### 测试要点

使用 `Object.is` 验证 `NaN` 与 `-0`；分别验证嵌套对象属性和数组中的 `undefined`。

覆盖 BigInt、无效 Date、Map 对象键、Set、用户自带 `$type` 字段、未知标签和重复对象键。

构造 `a.self = a`，断言错误同时包含 `$` 与 `$.self`。

函数、Symbol、DOM 节点应明确拒绝：它们没有跨进程可移植的值语义。

### 复写任务

合上答案后重新实现；然后扩展为“保留共享身份”的协议，并说明为何需要对象 ID 与两阶段解码。
