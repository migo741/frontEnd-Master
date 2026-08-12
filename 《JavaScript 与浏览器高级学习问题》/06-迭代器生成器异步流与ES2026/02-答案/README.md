# 第 06 章答案

## 练习 1：懒迭代管道

### 因果链

operator 只返回 generator factory，因此创建管道时不会读取 source。

map/filter 使用 for...of，消费者早退时语言会对其当前迭代器执行 IteratorClose。

take 需要精确控制 next 次数；达到上限后 finally 主动关闭仍未耗尽的上游。

### 可复制实现

```js
export const map = (mapper) => function mapOperator(iterable) {
  return {
    *[Symbol.iterator]() {
      let index = 0;
      for (const value of iterable) {
        yield mapper(value, index++);
      }
    },
  };
};

export const filter = (predicate) => function filterOperator(iterable) {
  return {
    *[Symbol.iterator]() {
      let index = 0;
      for (const value of iterable) {
        if (predicate(value, index++)) yield value;
      }
    },
  };
};

export const take = (count) => function takeOperator(iterable) {
  if (!Number.isInteger(count) || count < 0) throw new RangeError("count must be non-negative");
  return {
    *[Symbol.iterator]() {
      if (count === 0) return;
      const iterator = iterable[Symbol.iterator]();
      let exhausted = false;
      try {
        for (let seen = 0; seen < count; seen += 1) {
          const step = iterator.next();
          if (typeof step !== "object" || step === null) throw new TypeError("Bad iterator result");
          if (step.done) {
            exhausted = true;
            return;
          }
          yield step.value;
        }
      } finally {
        if (!exhausted) iterator.return?.();
      }
    },
  };
};

export function pipe(source, ...operators) {
  return operators.reduce((iterable, operator) => operator(iterable), source);
}
```

### 测试要点

```js
const calls = [];
const source = {
  [Symbol.iterator]() {
    let value = 0;
    return {
      next() { calls.push("next"); return { value: value++, done: false }; },
      return() { calls.push("return"); return { done: true }; },
    };
  },
};

const result = [...pipe(source, map((x) => x * 2), filter((x) => x % 4 === 0), take(3))];
assert.deepEqual(result, [0, 4, 8]);
assert.equal(calls.filter((x) => x === "return").length, 1);
```

创建管道后 calls 应为空，证明 lazy。

`take(0)` 后展开，连 `[Symbol.iterator]` 都不应请求，可另加 acquisition 计数。

消费者手动 break、mapper 抛错时仍断言底层 return 恰好一次。

### 边界与复写任务

返回对象是可重复 iterable，但若 source 自身只返回同一个 iterator，实际仍是一次性；包装层不能凭空恢复数据。

原生 Iterator Helpers 在可用环境中处理了更多规范细节，生产代码优先使用标准能力或成熟 polyfill。

合上答案重写，再实现 lazy flatMap，并验证内外两层 iterator 都能在早退时关闭。

## 练习 2：NDJSON 解码器

### 因果链

UTF-8 continuation byte 不会等于 LF 的 `0x0A`，因此可以先按字节找行，再对完整行解码。

每次只在下游请求 next 时继续 for-await 循环，所以不会主动拉取下一 chunk。

async generator 被 return/throw 时会退出 for-await；语言负责关闭当前上游 iterator。

### 可复制实现

```js
function abortReason(signal) {
  return signal?.reason ?? new DOMException("Aborted", "AbortError");
}

function checkAbort(signal) {
  if (signal?.aborted) throw abortReason(signal);
}

function appendBytes(left, right) {
  const output = new Uint8Array(left.length + right.length);
  output.set(left, 0);
  output.set(right, left.length);
  return output;
}

function parseLine(bytes, lineNumber) {
  if (bytes.at(-1) === 0x0d) bytes = bytes.subarray(0, bytes.length - 1);
  let text;
  try {
    text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch (cause) {
    throw new SyntaxError(`Invalid UTF-8 at NDJSON line ${lineNumber}`, { cause });
  }
  if (text.trim() === "") return { empty: true };
  try {
    return { empty: false, value: JSON.parse(text) };
  } catch (cause) {
    const summary = text.length > 120 ? `${text.slice(0, 120)}…` : text;
    throw new SyntaxError(`Invalid JSON at line ${lineNumber}: ${summary}`, { cause });
  }
}

export async function* decodeNDJSON(byteChunks, options = {}) {
  const signal = options.signal;
  const maxLineBytes = options.maxLineBytes ?? 1024 * 1024;
  if (!Number.isInteger(maxLineBytes) || maxLineBytes < 1) {
    throw new RangeError("maxLineBytes must be a positive integer");
  }

  let pending = new Uint8Array(0);
  let lineNumber = 1;

  for await (const chunk of byteChunks) {
    checkAbort(signal);
    if (!(chunk instanceof Uint8Array)) throw new TypeError("Chunks must be Uint8Array");
    pending = appendBytes(pending, chunk);
    let lineStart = 0;

    for (let index = 0; index < pending.length; index += 1) {
      if (pending[index] !== 0x0a) continue;
      const length = index - lineStart;
      if (length > maxLineBytes) {
        throw new RangeError(`NDJSON line ${lineNumber} exceeds ${maxLineBytes} bytes`);
      }
      const parsed = parseLine(pending.subarray(lineStart, index), lineNumber++);
      lineStart = index + 1;
      if (!parsed.empty) {
        yield parsed.value;
        checkAbort(signal);
      }
    }

    pending = pending.slice(lineStart);
    if (pending.length > maxLineBytes) {
      throw new RangeError(`NDJSON line ${lineNumber} exceeds ${maxLineBytes} bytes`);
    }
  }

  checkAbort(signal);
  if (pending.length > 0) {
    const parsed = parseLine(pending, lineNumber);
    if (!parsed.empty) yield parsed.value;
  }
}
```

### 测试要点

- 用 TextEncoder 编码含 emoji 的一行，在 emoji 四个字节中间切 chunk。
- 一个 chunk 放三行，另一个 JSON 行拆成五个 chunk。
- 分别测试 LF、CRLF、空白行和没有末尾换行。
- 注入非法 UTF-8 与非法 JSON，断言行号和 cause。
- 自定义上游在 finally 中记录 closed；消费一项后 break，断言 closed。
- 让上游每次 next 增加 pulled，消费端停在 yield 时 pulled 不应继续增加。

若环境支持，可用：

```js
const values = await Array.fromAsync(decodeNDJSON(chunks));
```

小输入的兼容测试也可手写 for-await 收集，不能让测试工具改变生产实现。

### 边界

若取消发生在等待上游 next 期间，而上游不观察同一个 signal，本函数无法强制打断那次等待。

真实 fetch/stream 适配器必须把 signal 继续传到底层 source。

`appendBytes` 对大量微小 chunk 可能重复复制；生产版可改用 chunk deque，并在发现完整行时再合并。

错误摘要可能含业务数据；线上日志应再做脱敏，本题只返回给直接调用者。

### 复写任务

合上答案重写；再增加 `transform(value, lineNumber)`，允许异步转换但仍严格保持单项背压和关闭传播。
