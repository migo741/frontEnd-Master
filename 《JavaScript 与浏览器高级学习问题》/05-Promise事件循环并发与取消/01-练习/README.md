# 第 05 章练习

第一题训练“只声称规范保证的顺序”，第二题训练任务所有权。

## 练习 1（经典必做）：事件循环偏序推演

在现代浏览器页面的普通 script 中分析：

```js
console.log("A");

setTimeout(() => {
  console.log("T");
  queueMicrotask(() => console.log("Tµ"));
}, 0);

const channel = new MessageChannel();
channel.port1.onmessage = () => console.log("M");
channel.port2.postMessage(null);

Promise.resolve().then(() => {
  console.log("P1");
  queueMicrotask(() => console.log("P2"));
});

queueMicrotask(() => {
  console.log("Q1");
  Promise.resolve().then(() => console.log("Q2"));
});

(async () => {
  console.log("I1");
  await null;
  console.log("I2");
})();

console.log("B");
```

要求：

1. 给出所有规范上可保证的先后关系，而不是只给一次浏览器输出。
2. 明确 `T` 与 `M` 是否有跨 task source 的固定顺序。
3. 说明 `Tµ` 相对另一个 task 的顺序。
4. 加入 rAF 后，解释为什么不能脱离渲染机会承诺唯一日志序列。
5. 在 DevTools Performance 中录制一次，并把实测与规范保证分开写。

## 练习 2（高难）：结构化限并发任务池

实现：

```js
await runPool(taskFunctions, {
  concurrency: 4,
  signal,
  stopOnError: false,
});
```

每个 task 是 `(signal, index) => value | Promise<value>`。

要求：

1. 同时运行数永不超过 concurrency，结果按输入位置排列。
2. `stopOnError:false` 返回 allSettled 形状，所有任务均被观察。
3. `stopOnError:true` 首个业务失败后停止启动新任务，取消已启动兄弟，结算后抛原始错误。
4. 外部 signal 取消后停止启动，向在途任务传播，结算后抛 `signal.reason`。
5. task 同步抛错、返回 thenable、空数组、非法并发数都要覆盖。
6. 不得产生 unhandled rejection；说明任务若忽略 signal 时的限制。

用可控 deferred Promise 证明上限、保序和每一种完成排列。
