# 第 01 章练习

只做两题。先写状态机和失败表，再写实现。

## 练习 1（经典必做）：可组合的异步资源作用域

用 TypeScript 实现 `ResourceScope`：

```ts
const scope = new ResourceScope();
scope.defer("db", async () => db.end());
scope.defer("telemetry", async () => telemetry.shutdown());
await scope.close(new Error("SIGTERM"));
```

不变量：

1. cleanup 按注册顺序的逆序运行。
2. `close` 幂等；并发调用得到同一个完成结果，每个 cleanup 恰好执行一次。
3. 一个 cleanup 失败不阻止后续项；结束后抛出带资源名称的 `AggregateError`。
4. 开始关闭后禁止注册新资源。
5. 每个 cleanup 都能读取同一个关闭原因。

验收至少覆盖：顺序、并发关闭、两个 cleanup 同时失败、关闭后注册。

## 练习 2（生产故障）：可排空的 HTTP 服务

只用 `node:http` 实现最小服务：

- `/live` 始终反映进程是否活着；`/ready` 只在 ready 状态返回 `200`。
- `/work?ms=...` 模拟可取消工作并返回 JSON。
- `shutdown(reason)` 先切为 draining，再停止接收新连接。
- 在途工作在总 deadline 内结束；deadline 到达后取消工作并强制关闭连接。
- 并发调用 `shutdown` 只执行一次，返回 `{ forced, activeAtStart }`。
- 库代码不得调用 `process.exit`；入口层再根据结果设置 `process.exitCode`。

写集成测试证明：关闭后 readiness 变红；在途短任务完成；长任务被取消；没有未观察的 rejection。

### 失败表必须包含

`SIGTERM` 重复到达、客户端提前断开、`server.close` 报错、deadline 到达、cleanup 失败。

### 复写要求

第一次可对照答案。第二次合上答案，把“立即取消在途工作”改为“先宽限、后取消”，并重新证明上限。
