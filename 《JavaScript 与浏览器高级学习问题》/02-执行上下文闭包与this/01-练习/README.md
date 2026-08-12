# 第 02 章练习

两题都要求严格模式运行，并证明接收者、返回值与清理语义。

## 练习 1（经典必做）：生产级 debounce

实现：

```js
function debounce(fn, wait, options = {}) {}
```

要求：

1. 默认 trailing 调用，可配置 `leading` 与 `trailing`。
2. 包装函数必须透传动态 `this` 和全部参数。
3. 提供 `cancel()`、`flush()`、`pending()`。
4. `flush()` 返回最近一次实际调用的结果；同步函数不能被强制改成 Promise。
5. 没有待执行调用时，`flush()` 不得重复执行 fn。
6. 用 fake timer 覆盖连续调用、leading-only、leading+trailing、取消与 flush。

先写状态表：空闲、等待、已 leading 调用，各事件如何迁移。

## 练习 2（高难）：不破坏语义的方法观测器

实现：

```js
const restore = observeMethod(object, key, hooks);
```

`hooks` 可含 `before(meta)`、`after(meta)`、`error(meta)`。

要求：

1. 保留调用时动态 `this`，不能永久绑定 object。
2. 保留参数、同步返回值和同步抛错；不能把同步方法统一改成 async。
3. 若返回 Promise/thenable，after/error 应在其完成后收到耗时与结果/错误。
4. `restore()` 幂等，只恢复自己安装的包装，不能覆盖后来者的修改。
5. hook 自身失败不能改变原方法结果，但应交给 `onHookError`。
6. 至少测试借用方法、class 私有字段、同步异常、异步拒绝和重复恢复。

说明你是否保留原 Promise 身份；若不保留，要写出这个取舍。
