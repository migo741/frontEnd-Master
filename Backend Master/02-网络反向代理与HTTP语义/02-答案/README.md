# 第 02 章答案

## 练习 1：可信代理请求上下文

### 可复制实现

```ts
// request-context.ts
import { isIP } from "node:net";

export type ContextInput = {
  remoteAddress: string;
  encrypted: boolean;
  forwardedFor?: string;
  forwardedProto?: string;
  forwardedHost?: string;
  socketHost: string;
  isTrustedProxy(ip: string): boolean;
  allowedHosts: ReadonlySet<string>;
};

function normalizeIp(raw: string): string {
  const value = raw.trim();
  const unwrapped = value.startsWith("[") && value.endsWith("]")
    ? value.slice(1, -1)
    : value;
  const normalized = unwrapped.startsWith("::ffff:")
    ? unwrapped.slice("::ffff:".length)
    : unwrapped;
  if (isIP(normalized) === 0) throw new TypeError(`invalid IP: ${raw}`);
  return normalized.toLowerCase();
}

function oneHeader(raw: string | undefined, name: string): string | undefined {
  if (raw === undefined) return undefined;
  if (raw.includes("\r") || raw.includes("\n")) throw new TypeError(`bad ${name}`);
  const value = raw.trim();
  if (!value || value.includes(",")) throw new TypeError(`ambiguous ${name}`);
  return value;
}

function normalizeHost(raw: string): string {
  const value = oneHeader(raw, "host")!;
  let url: URL;
  try { url = new URL(`http://${value}`); }
  catch { throw new TypeError("invalid host"); }
  if (url.username || url.password || url.pathname !== "/" || url.search || url.hash) {
    throw new TypeError("invalid host");
  }
  return url.host.toLowerCase();
}

export function resolveRequestContext(input: ContextInput) {
  const peer = normalizeIp(input.remoteAddress);
  const trustedPeer = input.isTrustedProxy(peer);
  let clientIp = peer;
  let scheme: "http" | "https" = input.encrypted ? "https" : "http";
  let host = normalizeHost(input.socketHost);

  if (trustedPeer) {
    const forwarded = input.forwardedFor?.split(",").map(normalizeIp) ?? [];
    if (forwarded.length > 16) throw new TypeError("too many proxy hops");
    const chain = [...forwarded, peer];
    let index = chain.length - 1;
    while (index > 0 && input.isTrustedProxy(chain[index]!)) index -= 1;
    clientIp = chain[index]!;

    const proto = oneHeader(input.forwardedProto, "proto")?.toLowerCase();
    if (proto !== undefined && proto !== "http" && proto !== "https") {
      throw new TypeError("invalid forwarded proto");
    }
    if (proto) scheme = proto;
    if (input.forwardedHost) host = normalizeHost(input.forwardedHost);
  }

  if (!input.allowedHosts.has(host)) throw new TypeError("host is not allowed");
  return { clientIp, scheme, host } as const;
}
```

### 测试矩阵

```ts
import assert from "node:assert/strict";
import test from "node:test";
import { resolveRequestContext } from "./request-context.js";

const trusted = new Set(["10.0.0.10", "10.0.0.11"]);
const base = {
  encrypted: false,
  socketHost: "api.example.com",
  isTrustedProxy: (ip: string) => trusted.has(ip),
  allowedHosts: new Set(["api.example.com"]),
};

test("ignores spoofed headers from direct client", () => {
  const result = resolveRequestContext({
    ...base,
    remoteAddress: "203.0.113.9",
    forwardedFor: "1.1.1.1",
    forwardedProto: "https",
  });
  assert.deepEqual(result, {
    clientIp: "203.0.113.9", scheme: "http", host: "api.example.com",
  });
});

test("walks trusted suffix from right to left", () => {
  const result = resolveRequestContext({
    ...base,
    remoteAddress: "::ffff:10.0.0.10",
    forwardedFor: "198.51.100.7, 10.0.0.11",
    forwardedProto: "https",
    forwardedHost: "api.example.com",
  });
  assert.equal(result.clientIp, "198.51.100.7");
  assert.equal(result.scheme, "https");
});

test("stops at untrusted hop injected into the chain", () => {
  const result = resolveRequestContext({
    ...base,
    remoteAddress: "10.0.0.10",
    forwardedFor: "1.1.1.1, 198.51.100.8",
  });
  assert.equal(result.clientIp, "198.51.100.8");
});
```

### 失败语义、验收与常见错误

非法 forwarding metadata 返回 `400`，不应“尽量猜”。真实生产用经过审计的 CIDR 库，并让部署测试验证代理究竟覆盖还是追加 header。client IP 只能用于审计和粗粒度防滥用，NAT、IPv6 隐私地址与代理都会让它不稳定。

常见错误是信任全部私网地址、只信固定 hop 数却未锁定拓扑、允许逗号分隔 proto/host 后随手取第一项，或把 IP 当账户身份。

### 复写任务

加入 RFC 7239 `Forwarded` adapter，但内部仍输出同一规范结构；对带引号、IPv6 和 `unknown` 标识写拒绝测试。

## 练习 2：条件请求

### 仓库与 handler

```ts
// document-server.ts
import http, { type IncomingMessage, type ServerResponse } from "node:http";

type DocumentState = { version: number; title: string };
let document: DocumentState = { version: 1, title: "first" };

const etag = (version: number) => `"v${version}"`;

function sendJson(res: ServerResponse, status: number, value: unknown, head = false): void {
  const body = Buffer.from(JSON.stringify(value));
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "content-length": body.length,
  });
  res.end(head ? undefined : body);
}

function problem(res: ServerResponse, status: number, type: string, title: string): void {
  const body = Buffer.from(JSON.stringify({ type, title, status }));
  res.writeHead(status, {
    "content-type": "application/problem+json",
    "content-length": body.length,
  });
  res.end(body);
}

async function readBody(req: IncomingMessage, limit: number): Promise<unknown> {
  const chunks: Buffer[] = [];
  let bytes = 0;
  for await (const chunk of req) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    bytes += buffer.length;
    if (bytes > limit) throw Object.assign(new Error("body too large"), { status: 413 });
    chunks.push(buffer);
  }
  try { return JSON.parse(Buffer.concat(chunks).toString("utf8")); }
  catch { throw Object.assign(new Error("invalid JSON"), { status: 400 }); }
}

export const server = http.createServer(async (req, res) => {
  const method = req.method ?? "GET";
  if (req.url !== "/document") return problem(res, 404, "not-found", "Not found");
  if (!["GET", "HEAD", "PUT"].includes(method)) {
    res.setHeader("allow", "GET, HEAD, PUT");
    return problem(res, 405, "method-not-allowed", "Method not allowed");
  }

  if (method === "GET" || method === "HEAD") {
    const tag = etag(document.version);
    res.setHeader("etag", tag);
    res.setHeader("cache-control", "private, no-cache");
    if (req.headers["if-none-match"] === tag) {
      res.writeHead(304);
      return res.end();
    }
    return sendJson(res, 200, document, method === "HEAD");
  }

  const expected = req.headers["if-match"];
  if (expected === undefined) return problem(res, 428, "precondition-required", "If-Match required");
  if (Array.isArray(expected) || expected === "*" || !/^"v\d+"$/.test(expected)) {
    return problem(res, 400, "bad-precondition", "One strong ETag required");
  }
  try {
    const input = await readBody(req, 16 * 1024);
    if (!input || typeof input !== "object" || typeof (input as { title?: unknown }).title !== "string") {
      return problem(res, 422, "invalid-document", "title must be a string");
    }
    // Body parsing above can yield. Version comparison must therefore happen here,
    // immediately before assignment, with no await in between.
    if (expected !== etag(document.version)) {
      return problem(res, 412, "precondition-failed", "Document changed");
    }
    document = { version: document.version + 1, title: (input as { title: string }).title };
    res.setHeader("etag", etag(document.version));
    return sendJson(res, 200, document);
  } catch (error) {
    const status = (error as { status?: number }).status ?? 500;
    return problem(res, status, "invalid-body", status === 413 ? "Body too large" : "Bad request");
  }
});
```

### 并发验收步骤

```ts
const first = await fetch(`${origin}/document`);
const tag = first.headers.get("etag")!;
const options = (title: string) => ({
  method: "PUT",
  headers: { "content-type": "application/json", "if-match": tag },
  body: JSON.stringify({ title }),
});
const [a, b] = await Promise.all([
  fetch(`${origin}/document`, options("A")),
  fetch(`${origin}/document`, options("B")),
]);
assert.deepEqual([a.status, b.status].sort(), [200, 412]);

const current = await fetch(`${origin}/document`);
const cached = await fetch(`${origin}/document`, {
  headers: { "if-none-match": current.headers.get("etag")! },
});
assert.equal(cached.status, 304);
assert.equal(await cached.text(), "");

const head = await fetch(`${origin}/document`, { method: "HEAD" });
assert.equal(await head.text(), "");
assert(Number(head.headers.get("content-length")) > 0);
```

### 边界、错误与复写

示例只支持一个强 ETag，故意拒绝列表、弱 ETag 与 `*`，让契约无歧义。生产仓库不能先 SELECT 再 UPDATE；应用等待数据库期间会发生并发写，应使用 `UPDATE ... WHERE version = $expected RETURNING ...` 并依据影响行数返回 `412`。

常见错误是比较版本后 `await` 解析或调用下游、把 ETag 当内容哈希却忘记编码变化、在 `304` 写 body，或允许 PUT 缺失前置条件而静默覆盖。

合上答案，把仓库抽象为 adapter；写一个故意在 compare 与 write 之间 yield 的坏实现，证明并发测试能稳定抓到丢失更新。
