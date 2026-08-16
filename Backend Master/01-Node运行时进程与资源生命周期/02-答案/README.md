# 第 01 章答案

## 练习 1：异步资源作用域

### 可复制实现

```ts
// resource-scope.ts
export type Cleanup = (reason: unknown) => void | Promise<void>;

type Entry = { name: string; cleanup: Cleanup };

export class ResourceScope {
  #state: "open" | "closing" | "closed" = "open";
  #entries: Entry[] = [];
  #closePromise: Promise<void> | undefined;

  defer(name: string, cleanup: Cleanup): void {
    if (this.#state !== "open") {
      throw new Error(`cannot register ${name}: scope is ${this.#state}`);
    }
    if (!name || typeof cleanup !== "function") {
      throw new TypeError("name and cleanup are required");
    }
    this.#entries.push({ name, cleanup });
  }

  close(reason: unknown): Promise<void> {
    if (this.#closePromise) return this.#closePromise;
    this.#state = "closing";
    this.#closePromise = this.#run(reason);
    return this.#closePromise;
  }

  async #run(reason: unknown): Promise<void> {
    const errors: Error[] = [];
    while (this.#entries.length > 0) {
      const entry = this.#entries.pop()!;
      try {
        await entry.cleanup(reason);
      } catch (cause) {
        errors.push(new Error(`cleanup failed: ${entry.name}`, { cause }));
      }
    }
    this.#state = "closed";
    if (errors.length > 0) {
      throw new AggregateError(errors, "one or more resources failed to close");
    }
  }
}
```

```ts
// resource-scope.test.ts
import assert from "node:assert/strict";
import test from "node:test";
import { ResourceScope } from "./resource-scope.js";

test("LIFO and exactly once", async () => {
  const scope = new ResourceScope();
  const calls: string[] = [];
  scope.defer("first", () => { calls.push("first"); });
  scope.defer("second", async () => { calls.push("second"); });

  const a = scope.close("stop");
  const b = scope.close("ignored second reason");
  assert.strictEqual(a, b);
  await a;
  assert.deepEqual(calls, ["second", "first"]);
  assert.throws(() => scope.defer("late", () => {}), /scope is closed/);
});

test("continues after cleanup failures", async () => {
  const scope = new ResourceScope();
  const calls: string[] = [];
  scope.defer("db", () => { calls.push("db"); throw new Error("db down"); });
  scope.defer("queue", () => { calls.push("queue"); throw new Error("queue down"); });

  await assert.rejects(scope.close("stop"), (error: unknown) => {
    assert(error instanceof AggregateError);
    assert.equal(error.errors.length, 2);
    assert.match(String(error.errors[0]), /queue/);
    assert.match(String(error.errors[1]), /db/);
    return true;
  });
  assert.deepEqual(calls, ["queue", "db"]);
});
```

### 失败语义与常见错误

`close` 第一次调用捕获关闭原因；后续原因不能改变已经启动的状态机。不要用 `forEach(async ...)`，它不会等待 cleanup。也不要在第一个异常处退出，否则数据库之外的 socket、遥测等资源会泄漏。

### 复写任务

合上答案，增加 `adopt(name, value, cleanup)`，返回原 value；证明资源注册失败时不会悄悄遗失 value。

## 练习 2：可排空 HTTP 服务

### 核心实现

```ts
// service.ts
import http, { type ServerResponse } from "node:http";
import { setTimeout as delay } from "node:timers/promises";

type State = "starting" | "ready" | "draining" | "stopped";
type ShutdownResult = { forced: boolean; activeAtStart: number };

function json(res: ServerResponse, status: number, body: unknown): void {
  const text = JSON.stringify(body);
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "content-length": Buffer.byteLength(text),
  });
  res.end(text);
}

export function createService(options: { shutdownMs: number }) {
  let state: State = "starting";
  let active = 0;
  let shutdownPromise: Promise<ShutdownResult> | undefined;
  let finishShutdown: (() => void) | undefined;
  const workAbort = new AbortController();

  const server = http.createServer(async (req, res) => {
    if (req.url === "/live") return json(res, 200, { live: state !== "stopped" });
    if (req.url === "/ready") {
      return json(res, state === "ready" ? 200 : 503, { state });
    }
    if (state !== "ready") return json(res, 503, { code: "DRAINING" });

    const url = new URL(req.url ?? "/", "http://service.local");
    if (url.pathname !== "/work") return json(res, 404, { code: "NOT_FOUND" });
    const ms = Number(url.searchParams.get("ms") ?? "0");
    if (!Number.isInteger(ms) || ms < 0 || ms > 60_000) {
      return json(res, 400, { code: "BAD_MS" });
    }

    active += 1;
    const requestAbort = new AbortController();
    const relay = () => requestAbort.abort(workAbort.signal.reason);
    workAbort.signal.addEventListener("abort", relay, { once: true });
    req.once("aborted", () => requestAbort.abort(new Error("client disconnected")));
    try {
      await delay(ms, undefined, { signal: requestAbort.signal });
      if (!res.destroyed) json(res, 200, { ok: true, ms });
    } catch (error) {
      if (!res.destroyed) json(res, 503, { code: "CANCELLED" });
    } finally {
      workAbort.signal.removeEventListener("abort", relay);
      active -= 1;
      finishShutdown?.();
    }
  });

  function listen(port = 0): Promise<number> {
    return new Promise((resolve, reject) => {
      server.once("error", reject);
      server.listen(port, "127.0.0.1", () => {
        server.off("error", reject);
        state = "ready";
        const address = server.address();
        if (!address || typeof address === "string") return reject(new Error("bad address"));
        resolve(address.port);
      });
    });
  }

  function shutdown(reason: unknown): Promise<ShutdownResult> {
    if (shutdownPromise) return shutdownPromise;
    state = "draining";
    const activeAtStart = active;
    shutdownPromise = new Promise<ShutdownResult>((resolve, reject) => {
      let forced = false;
      let serverClosed = false;
      let closeError: Error | undefined;
      const timer = setTimeout(() => {
        forced = true;
        workAbort.abort(reason);
        server.closeAllConnections();
      }, options.shutdownMs);
      timer.unref();

      const finish = () => {
        // closeAllConnections can make server.close's callback run before an
        // aborted handler reaches finally. Do not report stopped until both agree.
        if (!serverClosed || active !== 0) return;
        clearTimeout(timer);
        finishShutdown = undefined;
        state = "stopped";
        if (closeError) reject(closeError);
        else resolve({ forced, activeAtStart });
      };
      finishShutdown = finish;
      server.close((error) => {
        serverClosed = true;
        closeError = error;
        finish();
      });
    });
    return shutdownPromise;
  }

  return { listen, shutdown, get state() { return state; }, get active() { return active; } };
}
```

### 入口层与信号

```ts
// main.ts
import { createService } from "./service.js";

const service = createService({ shutdownMs: 10_000 });
await service.listen(Number(process.env.PORT ?? 3000));

for (const signal of ["SIGTERM", "SIGINT"] as const) {
  process.once(signal, () => {
    void service.shutdown(new Error(signal)).then(
      ({ forced }) => { process.exitCode = forced ? 1 : 0; },
      (error) => { console.error(error); process.exitCode = 1; },
    );
  });
}
```

### 集成测试关键片段

```ts
import assert from "node:assert/strict";
import test from "node:test";
import { createService } from "./service.js";

test("short request drains; repeated shutdown is identical", async () => {
  const service = createService({ shutdownMs: 500 });
  const port = await service.listen();
  const request = fetch(`http://127.0.0.1:${port}/work?ms=30`);
  await new Promise((resolve) => setTimeout(resolve, 5));
  const a = service.shutdown(new Error("test"));
  const b = service.shutdown(new Error("second"));
  assert.strictEqual(a, b);
  assert.equal(service.state, "draining");
  assert.equal((await request).status, 200);
  assert.deepEqual(await a, { forced: false, activeAtStart: 1 });
  assert.equal(service.active, 0);
});

test("deadline cancels long work", async () => {
  const service = createService({ shutdownMs: 20 });
  const port = await service.listen();
  const request = fetch(`http://127.0.0.1:${port}/work?ms=500`).catch(() => undefined);
  await new Promise((resolve) => setTimeout(resolve, 5));
  const result = await service.shutdown(new Error("deadline"));
  await request;
  assert.equal(result.forced, true);
  assert.equal(service.active, 0);
});
```

### 边界与验收

生产部署通常先把 readiness 置红，再等待负载均衡传播时间，之后调用 `server.close`；示例省略这段平台相关宽限。HTTP/2、升级连接和独立后台消费者需要各自的 close adapter。`closeAllConnections` 是 deadline 后的保险，会中断响应，因此 `forced: true` 必须告警。

常见错误是收到信号立即 abort 所有短请求、在库函数里调用 `process.exit`、忘记监听客户端断开，或用未 `unref` 的定时器阻止进程结束。

### 复写任务

实现 `graceMs`：先停止接流量并允许任务自然结束，宽限到期才广播 abort，最终 deadline 才销毁连接；为三个时间点使用同一个绝对 deadline。
