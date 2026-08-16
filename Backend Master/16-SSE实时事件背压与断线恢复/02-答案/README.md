# 第 16 章答案

下面给的是可以落到 Fastify/Node 项目的核心实现。仓储和订阅适配器应连接第 13、14 章的持久任务与 Outbox，而不是进程内 `EventEmitter`。

## 练习一答案：可断点续传的 SSE 工单流

先定义边界：

```ts
import { once } from "node:events";
import type { ServerResponse } from "node:http";

export type RunEvent = Readonly<{
  runId: string;
  tenantId: string;
  seq: number;
  type: string;
  payload: unknown;
  occurredAt: string;
}>;

export interface RunEventRepository {
  runExists(input: { tenantId: string; runId: string }): Promise<boolean>;
  replay(input: {
    tenantId: string;
    runId: string;
    after: number;
    limit: number;
  }): Promise<readonly RunEvent[]>;
  subscribe(input: {
    tenantId: string;
    runId: string;
    after: number;
    signal: AbortSignal;
  }): AsyncIterable<RunEvent>;
}

const TERMINAL = new Set([
  "run.succeeded",
  "run.failed",
  "run.cancelled",
]);

function frame(event: RunEvent): string {
  const data = JSON.stringify({
    version: 1,
    runId: event.runId,
    seq: event.seq,
    occurredAt: event.occurredAt,
    type: event.type,
    payload: event.payload,
  });
  return `id: ${event.seq}\nevent: ${event.type}\ndata: ${data}\n\n`;
}

async function writeWithBackpressure(
  response: ServerResponse,
  chunk: string,
  signal: AbortSignal,
): Promise<void> {
  if (signal.aborted) throw signal.reason;
  if (response.write(chunk)) return;
  await once(response, "drain", { signal });
}

function parseCursor(value: string | undefined): number {
  if (value === undefined || value === "") return 0;
  if (!/^\d+$/.test(value)) throw new Error("INVALID_CURSOR");
  const cursor = Number(value);
  if (!Number.isSafeInteger(cursor)) throw new Error("INVALID_CURSOR");
  return cursor;
}
```

路由中的“唯一写者”顺序化所有帧，避免心跳与业务帧并发交错：

```ts
type Auth = Readonly<{ tenantId: string; userId: string }>;

export function registerRunEventsRoute(
  app: import("fastify").FastifyInstance,
  repo: RunEventRepository,
) {
  app.get<{ Params: { runId: string } }>(
    "/api/runs/:runId/events",
    async (request, reply) => {
      const auth = (request as typeof request & { user: Auth }).user;
      let cursor: number;
      try {
        const rawCursor = request.headers["last-event-id"];
        cursor = parseCursor(Array.isArray(rawCursor) ? rawCursor[0] : rawCursor);
      } catch {
        return reply.code(400).send({ code: "INVALID_LAST_EVENT_ID" });
      }

      const visible = await repo.runExists({
        tenantId: auth.tenantId,
        runId: request.params.runId,
      });
      if (!visible) return reply.code(404).send({ code: "NOT_FOUND" });

      reply.hijack();
      const response = reply.raw;
      response.writeHead(200, {
        "content-type": "text/event-stream; charset=utf-8",
        "cache-control": "no-cache, no-transform",
        connection: "keep-alive",
        "x-accel-buffering": "no",
      });
      response.flushHeaders();

      const connection = new AbortController();
      const onClose = () => connection.abort(new Error("CLIENT_CLOSED"));
      response.once("close", onClose);
      const deadline = setTimeout(
        () => connection.abort(new Error("STREAM_DEADLINE")),
        30 * 60_000,
      );
      deadline.unref();

      let chain: Promise<void> = Promise.resolve();
      let queuedBytes = 0;
      const MAX_QUEUED_BYTES = 1024 * 1024;
      const enqueue = (chunk: string) => {
        const bytes = Buffer.byteLength(chunk);
        if (queuedBytes + bytes > MAX_QUEUED_BYTES) {
          connection.abort(new Error("SLOW_CONSUMER"));
          return Promise.reject(connection.signal.reason);
        }
        queuedBytes += bytes;
        const task = chain.then(() =>
          writeWithBackpressure(response, chunk, connection.signal),
        );
        chain = task.catch(() => undefined);
        return task.finally(() => { queuedBytes -= bytes; });
      };

      let heartbeatPending = false;
      const heartbeat = setInterval(() => {
        if (heartbeatPending) return;
        heartbeatPending = true;
        void enqueue(`: heartbeat ${Date.now()}\n\n`)
          .catch(() => undefined)
          .finally(() => { heartbeatPending = false; });
      }, 15_000);
      heartbeat.unref();

      try {
        while (true) {
          const history = await repo.replay({
            tenantId: auth.tenantId,
            runId: request.params.runId,
            after: cursor,
            limit: 1_000,
          });
          for (const event of history) {
            if (event.seq <= cursor) continue;
            await enqueue(frame(event));
            cursor = event.seq;
            if (TERMINAL.has(event.type)) return;
          }
          if (history.length < 1_000) break;
        }

        for await (const event of repo.subscribe({
          tenantId: auth.tenantId,
          runId: request.params.runId,
          after: cursor,
          signal: connection.signal,
        })) {
          if (event.seq <= cursor) continue;
          if (event.seq !== cursor + 1) {
            await enqueue(
              `event: stream.reset\ndata: ${JSON.stringify({ after: cursor })}\n\n`,
            );
            return;
          }
          await enqueue(frame(event));
          cursor = event.seq;
          if (TERMINAL.has(event.type)) return;
        }
      } catch (error) {
        if (!connection.signal.aborted) request.log.error({ error, cursor });
      } finally {
        clearInterval(heartbeat);
        clearTimeout(deadline);
        response.off("close", onClose);
        if (!response.writableEnded) response.end();
      }
    },
  );
}
```

生产版还应让 `enqueue` 有待发送字节上限。超过上限时记录 `slow_consumer` 并断开，不能让 Promise 链无限增长。

关键测试可用一个第一次 `write()` 返回 `false` 的 fake response，断言第二帧在触发 `drain` 之前没有写入。测试断连时只断言 `subscribe.signal.aborted === true`，不要调用业务取消函数。

失败语义：

- 历史超过单次回放上限：发送 `stream.reset`，客户端获取快照；
- 写入背压长期不恢复：关闭传输，run 不受影响；
- 订阅层报错：连接结束并由客户端重连；
- terminal 已发送：正常 `end()`，不再心跳。

## 练习二答案：可恢复的 Agent 事件协议

协议只允许 JSON 值，客户端投影显式处理缺口和冲突：

```ts
type Json = null | boolean | number | string | Json[] | { [k: string]: Json };

export type WireEvent = Readonly<{
  version: 1;
  runId: string;
  seq: number;
  occurredAt: string;
  type:
    | "run.started"
    | "run.token"
    | "run.step"
    | "tool.proposed"
    | "tool.approval_required"
    | "tool.completed"
    | "run.failed"
    | "run.succeeded"
    | "run.cancelled";
  payload: Json;
}>;

type Projection = Readonly<{
  runId: string;
  lastSeq: number;
  status: "idle" | "running" | "waiting_approval" | "succeeded" | "failed" | "cancelled";
  text: string;
  fingerprints: ReadonlyMap<number, string>;
}>;

type ApplyResult =
  | { kind: "applied" | "duplicate"; state: Projection }
  | { kind: "needs_snapshot"; after: number }
  | { kind: "corrupt"; seq: number };

function fingerprint(event: WireEvent): string {
  return JSON.stringify(event);
}

export function applyEvent(state: Projection, event: WireEvent): ApplyResult {
  if (event.version !== 1 || event.runId !== state.runId) {
    return { kind: "needs_snapshot", after: state.lastSeq };
  }
  if (event.seq <= state.lastSeq) {
    return state.fingerprints.get(event.seq) === fingerprint(event)
      ? { kind: "duplicate", state }
      : { kind: "corrupt", seq: event.seq };
  }
  if (event.seq !== state.lastSeq + 1) {
    return { kind: "needs_snapshot", after: state.lastSeq };
  }
  if (["succeeded", "failed", "cancelled"].includes(state.status)) {
    return { kind: "corrupt", seq: event.seq };
  }

  let status = state.status;
  let text = state.text;
  if (event.type === "run.started") status = "running";
  if (event.type === "run.token") {
    const token = (event.payload as { text?: Json }).text;
    if (typeof token !== "string") return { kind: "corrupt", seq: event.seq };
    text += token;
  }
  if (event.type === "tool.approval_required") status = "waiting_approval";
  if (event.type === "tool.completed") status = "running";
  if (event.type === "run.succeeded") status = "succeeded";
  if (event.type === "run.failed") status = "failed";
  if (event.type === "run.cancelled") status = "cancelled";

  const fingerprints = new Map(state.fingerprints);
  fingerprints.set(event.seq, fingerprint(event));
  return {
    kind: "applied",
    state: { ...state, lastSeq: event.seq, status, text, fingerprints },
  };
}
```

取消端点的服务层使用数据库条件更新，天然幂等：

```sql
update agent_runs
set cancel_requested_at = coalesce(cancel_requested_at, now())
where tenant_id = $1
  and id = $2
  and status in ('queued', 'running', 'waiting_approval')
returning id, cancel_requested_at;
```

如果没有返回行，再查询同租户 run：已经终态时返回当前状态，不存在或跨租户统一 `404`。连接的 AbortController 只管理订阅；任务取消由数据库状态和队列 worker 观察。

验收清单：

- 用固定 fixture 测试重复事件内容冲突；
- 先发送 terminal，再发送 token，必须得到 `corrupt`；
- 丢掉中间 seq，必须 `needs_snapshot`；
- 两次取消只记录一次时间；
- 关闭 SSE 不改变 `cancel_requested_at`；
- 代理缓冲关闭且 15 秒内能看到心跳。

常见错误：用内存计数器生成序号、把 token 当权威数据、不等 `drain`、在 `close` 里取消业务、只靠 EventSource 自动重连却没有持久回放。

复写任务：关掉答案，从空文件重写 `writeWithBackpressure`、回放/订阅去重和 terminal 防迟到逻辑，再画出业务状态机与传输状态机。
