# 第 03 章答案

## 练习 1：一次性配置编译器

### 可复制实现

```ts
// config.ts
import { inspect } from "node:util";

type AppEnv = "development" | "test" | "production";
type LogLevel = "debug" | "info" | "warn" | "error";

export class SecretString {
  #value: string;
  constructor(value: string) { this.#value = value; }
  reveal(): string { return this.#value; }
  toJSON(): string { return "[REDACTED]"; }
  toString(): string { return "[REDACTED]"; }
  [inspect.custom](): string { return "SecretString([REDACTED])"; }
}

export type Config = Readonly<{
  env: AppEnv;
  port: number;
  databaseUrl: URL;
  logLevel: LogLevel;
  modelApiKey: SecretString;
}>;

const allowed = new Set([
  "APP_ENV", "APP_PORT", "APP_DATABASE_URL", "APP_LOG_LEVEL", "APP_MODEL_API_KEY",
]);

export function loadConfig(env: Readonly<Record<string, string | undefined>>): Config {
  const issues: string[] = [];
  for (const key of Object.keys(env).filter((key) => key.startsWith("APP_"))) {
    if (!allowed.has(key)) issues.push(`${key}: unknown setting`);
  }

  function required(name: string): string {
    const value = env[name];
    if (value === undefined || value.trim() === "") {
      issues.push(`${name}: required`);
      return "";
    }
    return value.trim();
  }

  const rawEnv = required("APP_ENV");
  const appEnv = (["development", "test", "production"] as const).find((v) => v === rawEnv);
  if (!appEnv && rawEnv) issues.push("APP_ENV: unsupported value");

  const rawPort = env.APP_PORT?.trim() || "3000";
  const port = /^\d+$/.test(rawPort) ? Number(rawPort) : Number.NaN;
  if (!Number.isInteger(port) || port < 1 || port > 65_535) {
    issues.push("APP_PORT: expected integer 1..65535");
  }

  const rawLevel = env.APP_LOG_LEVEL?.trim() || "info";
  const logLevel = (["debug", "info", "warn", "error"] as const).find((v) => v === rawLevel);
  if (!logLevel) issues.push("APP_LOG_LEVEL: unsupported value");

  const rawDatabaseUrl = required("APP_DATABASE_URL");
  let databaseUrl: URL | undefined;
  try {
    databaseUrl = new URL(rawDatabaseUrl);
    if (!["postgres:", "postgresql:"].includes(databaseUrl.protocol)) {
      issues.push("APP_DATABASE_URL: expected PostgreSQL URL");
    }
    if (appEnv === "production" && databaseUrl.searchParams.get("sslmode") !== "require") {
      issues.push("APP_DATABASE_URL: production requires sslmode=require");
    }
  } catch {
    if (rawDatabaseUrl) issues.push("APP_DATABASE_URL: invalid URL");
  }

  const rawKey = required("APP_MODEL_API_KEY");
  if (issues.length > 0) {
    throw new AggregateError(issues.map((message) => new Error(message)), "invalid configuration");
  }

  return Object.freeze({
    env: appEnv!, port, databaseUrl: databaseUrl!, logLevel: logLevel!,
    modelApiKey: Object.freeze(new SecretString(rawKey)),
  });
}
```

### 测试要点

```ts
import assert from "node:assert/strict";
import test from "node:test";
import { inspect } from "node:util";
import { loadConfig } from "./config.js";

const valid = {
  APP_ENV: "production",
  APP_PORT: "3000",
  APP_DATABASE_URL: "postgresql://app:secret@db/app?sslmode=require",
  APP_LOG_LEVEL: "info",
  APP_MODEL_API_KEY: "top-secret",
};

test("parses, freezes and redacts", () => {
  const config = loadConfig(valid);
  assert(Object.isFrozen(config));
  assert.equal(config.port, 3000);
  assert.equal(config.modelApiKey.reveal(), "top-secret");
  assert(!JSON.stringify(config).includes("top-secret"));
  assert(!inspect(config).includes("top-secret"));
});

test("reports every issue", () => {
  assert.throws(() => loadConfig({
    APP_ENV: "prod", APP_PORT: "3000x", APP_DATABASE_URL: "http://db",
    APP_MODEL_API_KEY: "", APP_TYPO: "x",
  }), (error: unknown) => {
    assert(error instanceof AggregateError);
    assert(error.errors.length >= 5);
    return true;
  });
});
```

### 失败语义与常见错误

配置错误是启动失败，不是请求期 `500`。生产 TLS 规则应与所用驱动/云数据库契约一致，示例只演示原则。不要记录完整 URL：其中可能含密码。`Object.freeze` 是防误改，不是秘密安全机制。

复写：增加 `APP_REQUEST_TIMEOUT_MS`，要求 100–30_000，且必须小于部署层给出的外部 timeout。

## 练习 2：框架无关创建工单

### Domain 与 application

```ts
// application/create-ticket.ts
export type Priority = "low" | "normal" | "high";
export type AuthContext = Readonly<{ tenantId: string; userId: string }>;
export type CreateTicketCommand = Readonly<{ title: string; priority: Priority }>;
export type Ticket = Readonly<{
  id: string; tenantId: string; title: string; priority: Priority;
  createdBy: string; createdAt: Date;
}>;

export interface TicketWriter { insert(ticket: Ticket): Promise<void> }
export interface Clock { now(): Date }
export interface IdGenerator { next(): string }

export class InputError extends Error {
  readonly code = "INVALID_TICKET";
}

export function createCreateTicket(deps: {
  writer: TicketWriter; clock: Clock; ids: IdGenerator;
}) {
  return async (auth: AuthContext, command: CreateTicketCommand): Promise<Ticket> => {
    const title = command.title.trim();
    if (title.length < 3 || title.length > 200) {
      throw new InputError("title must contain 3..200 characters");
    }
    const ticket: Ticket = Object.freeze({
      id: deps.ids.next(), tenantId: auth.tenantId, title,
      priority: command.priority, createdBy: auth.userId,
      createdAt: deps.clock.now(),
    });
    await deps.writer.insert(ticket);
    return ticket;
  };
}
```

### Runtime parser

```ts
// adapters/http/parse-create-ticket.ts
import type { CreateTicketCommand, Priority } from "../../application/create-ticket.js";

const priorities = new Set<Priority>(["low", "normal", "high"]);

export function parseCreateTicket(value: unknown): CreateTicketCommand {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new TypeError("body must be an object");
  }
  const body = value as Record<string, unknown>;
  const keys = Object.keys(body);
  if (keys.some((key) => !["title", "priority"].includes(key))) {
    throw new TypeError("unknown field");
  }
  if (typeof body.title !== "string" || typeof body.priority !== "string" ||
      !priorities.has(body.priority as Priority)) {
    throw new TypeError("invalid title or priority");
  }
  return { title: body.title, priority: body.priority as Priority };
}
```

### 薄 HTTP adapter

```ts
fastify.post("/tickets", async (request, reply) => {
  try {
    const auth = request.auth; // 由可信认证插件建立；不得来自 body/header
    const command = parseCreateTicket(request.body);
    const ticket = await createTicket(auth, command);
    return reply.code(201).send(ticket);
  } catch (error) {
    if (error instanceof TypeError || error instanceof InputError) {
      return reply.code(422).send({ type: "invalid-ticket", status: 422 });
    }
    request.log.error({ err: error }, "create ticket failed");
    return reply.code(500).send({ type: "internal", status: 500 });
  }
});
```

### 用例测试

```ts
import assert from "node:assert/strict";
import test from "node:test";
import { createCreateTicket, type Ticket } from "./create-ticket.js";
import { parseCreateTicket } from "../adapters/http/parse-create-ticket.js";

test("trusted context owns tenant and creator", async () => {
  const saved: Ticket[] = [];
  const create = createCreateTicket({
    writer: { async insert(ticket) { saved.push(ticket); } },
    clock: { now: () => new Date("2026-08-16T00:00:00Z") },
    ids: { next: () => "ticket-1" },
  });
  const ticket = await create(
    { tenantId: "tenant-a", userId: "user-1" },
    parseCreateTicket({ title: " Printer broken ", priority: "high" }),
  );
  assert.deepEqual(ticket, {
    id: "ticket-1", tenantId: "tenant-a", title: "Printer broken",
    priority: "high", createdBy: "user-1", createdAt: new Date("2026-08-16T00:00:00Z"),
  });
  assert.strictEqual(saved[0], ticket);
});

test("body cannot select tenant", () => {
  assert.throws(() => parseCreateTicket({
    title: "valid title", priority: "normal", tenantId: "victim",
  }), /unknown field/);
});
```

### 验收、常见错误与复写

未识别 repository 异常只记录内部 cause，公开响应不带 SQL、路径或堆栈。真实 adapter 还要设置稳定 Problem Details、request ID，并由统一 error handler 完成映射。

常见错误是 parser 返回 `any`、把 `request` 传入 use case、在 domain 内生成当前时间、或为了测试 mock 整个框架。

合上答案，用同一 `createTicket` 写一个队列 consumer；消息 schema 必须重新验证，租户则来自已验证消息 envelope，而非 payload 中可覆盖字段。
