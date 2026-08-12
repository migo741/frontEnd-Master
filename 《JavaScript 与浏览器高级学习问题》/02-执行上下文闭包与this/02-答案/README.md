# 第 02 章答案

## 练习 1：生产级 debounce

### 因果链

闭包保存 timer、最近参数、最近接收者和最近结果。

动态 this 必须在包装函数被调用时记录，不能在创建 debounce 时猜测。

leading 决定等待窗口开头是否调用；trailing 决定窗口结束是否调用。

当同时启用 leading/trailing 时，只有窗口内发生了后续调用，结尾才需再次执行。

### 可复制实现

```js
export function debounce(fn, wait, options = {}) {
  if (typeof fn !== "function") throw new TypeError("fn must be a function");
  const leading = options.leading ?? false;
  const trailing = options.trailing ?? true;
  let timer = null;
  let lastArgs;
  let lastThis;
  let result;
  let trailingRequested = false;

  function invoke() {
    const args = lastArgs;
    const receiver = lastThis;
    lastArgs = lastThis = undefined;
    trailingRequested = false;
    result = Reflect.apply(fn, receiver, args);
    return result;
  }

  function onTimeout() {
    timer = null;
    if (trailing && trailingRequested && lastArgs) invoke();
    else lastArgs = lastThis = undefined;
  }

  function debounced(...args) {
    const wasIdle = timer === null;
    lastArgs = args;
    lastThis = this;

    if (wasIdle) {
      trailingRequested = !leading;
      timer = setTimeout(onTimeout, wait);
      if (leading) return invoke();
      return result;
    }

    trailingRequested = true;
    clearTimeout(timer);
    timer = setTimeout(onTimeout, wait);
    return result;
  }

  debounced.cancel = () => {
    if (timer !== null) clearTimeout(timer);
    timer = null;
    lastArgs = lastThis = undefined;
    trailingRequested = false;
  };

  debounced.flush = () => {
    if (timer === null) return result;
    clearTimeout(timer);
    timer = null;
    if (trailing && trailingRequested && lastArgs) return invoke();
    lastArgs = lastThis = undefined;
    trailingRequested = false;
    return result;
  };

  debounced.pending = () => timer !== null;
  return debounced;
}
```

### 测试要点

- 用对象的 `method` 调用包装器，断言 fn 内的 this 就是该对象。
- 连续三次调用，推进时间，断言只收到最后一组参数。
- leading-only 首次立即执行，窗口内调用不执行，窗口后可再次执行。
- leading+trailing 只有一次调用时不重复；有第二次时窗口尾执行一次。
- cancel 后推进时间没有调用；flush 只执行一次且返回原结果。

### 边界

本实现是“静默期 debounce”：窗口会被每次调用向后延长。

它没有 maxWait；若业务需要最长等待，应增加独立 maxTimer，而不是混用同一计时器。

### 复写任务

合上答案，从状态表重写；随后增加 `maxWait`，测试持续输入时仍周期执行。

## 练习 2：方法观测器

### 因果链

方法被谁调用，this 就应继续是谁，所以包装器必须是普通函数并使用 Reflect.apply。

同步调用用 try/catch 保持同步；只有检测到 thenable 后才接入完成通知。

hook 是旁路观测，不能让它的异常污染业务调用。

恢复时比较当前函数身份，可避免覆盖安装后发生的其他修改。

### 可复制实现

```js
const now = () => performance.now();

export function observeMethod(object, key, hooks = {}) {
  const original = object[key];
  if (typeof original !== "function") throw new TypeError(`${String(key)} is not callable`);
  const reportHookError = hooks.onHookError ?? (() => {});

  function safeHook(name, meta) {
    try {
      hooks[name]?.(meta);
    } catch (error) {
      try { reportHookError(error, name, meta); } catch {}
    }
  }

  function wrapped(...args) {
    const receiver = this;
    const startedAt = now();
    const base = { key, receiver, args, startedAt };
    safeHook("before", base);

    let output;
    try {
      output = Reflect.apply(original, receiver, args);
    } catch (error) {
      safeHook("error", { ...base, duration: now() - startedAt, error });
      throw error;
    }

    const then = output != null &&
      (typeof output === "object" || typeof output === "function") &&
      typeof output.then === "function";

    if (!then) {
      safeHook("after", { ...base, duration: now() - startedAt, result: output });
      return output;
    }

    return Promise.resolve(output).then(
      (result) => {
        safeHook("after", { ...base, duration: now() - startedAt, result });
        return result;
      },
      (error) => {
        safeHook("error", { ...base, duration: now() - startedAt, error });
        throw error;
      },
    );
  }

  object[key] = wrapped;
  let restored = false;
  return function restore() {
    if (restored) return false;
    restored = true;
    if (object[key] !== wrapped) return false;
    object[key] = original;
    return true;
  };
}
```

### 测试要点

```js
class Counter {
  #value = 1;
  add(n) { this.#value += n; return this.#value; }
}

const counter = new Counter();
const restore = observeMethod(counter, "add", { after: () => {} });
assert.equal(counter.add(2), 3); // private brand 要求 this 仍是 counter
assert.equal(restore(), true);
assert.equal(restore(), false);
```

再测试 `const borrowed = object.method; borrowed.call(other, 1)`，接收者应是 other。

让原方法同步抛错，断言 error hook 执行且原错误对象原样抛出。

让原方法返回拒绝的 Promise，断言 error hook 最终执行且拒绝原因不变。

让 after 主动抛错，断言业务返回值仍正确且 onHookError 收到错误。

### 边界与取舍

参考实现对 thenable 返回一个接续后的新 Promise，因此不保留 Promise 身份，但保留兑现值与拒绝原因。

若调用方依赖 Promise 身份，可在原 Promise 上注册旁路回调后返回原对象；同时要谨慎处理 thenable 的副作用 getter。

本简化实现也没有保留属性 descriptor；下一章学习 descriptor 后应升级为 descriptor-aware 版本。

### 复写任务

合上答案重写，并增加并发调用 ID，使日志能正确配对每一次开始和完成。
