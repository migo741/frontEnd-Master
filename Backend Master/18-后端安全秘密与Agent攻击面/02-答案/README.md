# 第 18 章答案

## 练习一答案：防 DNS Rebinding 的受限 URL 抓取器

下面实现依赖 `undici` 与 `ipaddr.js`。精确 allowlist 是第一层，DNS/IP 校验和 pinning 是第二层，生产 egress proxy/NetworkPolicy 是第三层。

```ts
import { Agent, fetch } from "undici";
import { resolve4, resolve6 } from "node:dns/promises";
import ipaddr from "ipaddr.js";
import { createHash } from "node:crypto";

type FetchPolicy = Readonly<{
  allowedHosts: ReadonlySet<string>;
  allowedContentTypes: ReadonlySet<string>;
  maxBytes: number;
  maxRedirects: number;
  timeoutMs: number;
}>;

function publicAddress(raw: string): boolean {
  let address = ipaddr.parse(raw);
  if (address.kind() === "ipv6" && address.isIPv4MappedAddress()) {
    address = address.toIPv4Address();
  }
  return address.range() === "unicast";
}

async function resolveAndValidate(hostname: string) {
  const [v4, v6] = await Promise.all([
    resolve4(hostname).catch(() => []),
    resolve6(hostname).catch(() => []),
  ]);
  const values = [
    ...v4.map((address) => ({ address, family: 4 as const })),
    ...v6.map((address) => ({ address, family: 6 as const })),
  ];
  if (values.length === 0) throw new Error("DNS_EMPTY");
  if (values.some(({ address }) => !publicAddress(address))) {
    throw new Error("DNS_NON_PUBLIC_ADDRESS");
  }
  return values[0]!;
}

function validateUrl(raw: string, policy: FetchPolicy): URL {
  const url = new URL(raw);
  const hostname = url.hostname.toLowerCase();
  if (url.protocol !== "https:") throw new Error("SCHEME_DENIED");
  if (url.username || url.password) throw new Error("URL_CREDENTIALS_DENIED");
  if (url.port && url.port !== "443") throw new Error("PORT_DENIED");
  if (!policy.allowedHosts.has(hostname)) throw new Error("HOST_DENIED");
  return url;
}

async function readBounded(
  response: import("undici").Response,
  maxBytes: number,
): Promise<Uint8Array> {
  const declared = Number(response.headers.get("content-length"));
  if (Number.isFinite(declared) && declared > maxBytes) throw new Error("BODY_TOO_LARGE");
  if (!response.body) return new Uint8Array();
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > maxBytes) throw new Error("BODY_TOO_LARGE");
      chunks.push(value);
    }
  } finally {
    if (total > maxBytes) await reader.cancel().catch(() => undefined);
  }
  const output = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    output.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return output;
}

export async function restrictedFetch(raw: string, policy: FetchPolicy) {
  const deadline = AbortSignal.timeout(policy.timeoutMs);
  let current = raw;
  for (let redirect = 0; redirect <= policy.maxRedirects; redirect += 1) {
    const url = validateUrl(current, policy);
    const resolved = await resolveAndValidate(url.hostname);
    const dispatcher = new Agent({
      connect: {
        servername: url.hostname,
        lookup(_hostname, _options, callback) {
          callback(null, resolved.address, resolved.family);
        },
      },
    });
    try {
      const response = await fetch(url, {
        method: "GET",
        redirect: "manual",
        signal: deadline,
        dispatcher,
        headers: { accept: [...policy.allowedContentTypes].join(", ") },
      });
      if ([301, 302, 303, 307, 308].includes(response.status)) {
        const location = response.headers.get("location");
        if (!location || redirect === policy.maxRedirects) {
          throw new Error("REDIRECT_DENIED");
        }
        current = new URL(location, url).toString();
        await response.body?.cancel();
        continue;
      }
      if (!response.ok) throw new Error(`UPSTREAM_${response.status}`);
      const contentType = response.headers.get("content-type")?.split(";", 1)[0]?.trim();
      if (!contentType || !policy.allowedContentTypes.has(contentType)) {
        throw new Error("CONTENT_TYPE_DENIED");
      }
      const body = await readBounded(response, policy.maxBytes);
      return {
        body,
        contentType,
        finalHost: url.hostname,
        resolvedAddress: resolved.address,
        urlHash: createHash("sha256").update(url.origin + url.pathname).digest("hex"),
      };
    } finally {
      await dispatcher.close();
    }
  }
  throw new Error("REDIRECT_DENIED");
}
```

注意：`ipaddr.js` 的 `unicast` 判定仍需通过依赖升级跟踪地址分类；企业环境最好只允许业务明确列出的域和 egress proxy。不要把最终 URL query 写日志。

用自定义 DNS resolver 和本地测试服务器制造“校验时公网、连接时私网”的 rebinding；断言 pinned lookup 始终连接已检查地址。对每次 redirect 断言重新调用 resolver。

## 练习二答案：Prompt Injection 下仍最小权限的工具执行器

工具目录由可信代码构建，模型只能选择其中条目：

```ts
import { z } from "zod";

type Capability = Readonly<{
  action: string;
  resourceId: string;
  tenantId: string;
  expiresAtMs: number;
}>;

type Context = Readonly<{
  tenantId: string;
  runId: string;
  deadlineMs: number;
  maxCalls: number;
  capabilities: readonly Capability[];
}>;

type Tool<A> = Readonly<{
  schema: z.ZodType<A>;
  action: string;
  resourceId: (args: A) => string;
  run: (args: A, signal: AbortSignal) => Promise<unknown>;
}>;

export class ToolRunner {
  #calls = 0;
  constructor(
    private readonly context: Context,
    private readonly tools: Readonly<Record<string, Tool<unknown>>>,
  ) {}

  async call(name: string, rawArgs: unknown): Promise<unknown> {
    if (this.#calls >= this.context.maxCalls) throw new Error("TOOL_BUDGET_EXCEEDED");
    if (Date.now() >= this.context.deadlineMs) throw new Error("RUN_DEADLINE_EXCEEDED");
    const tool = this.tools[name];
    if (!tool) throw new Error("TOOL_DENIED");
    const args = tool.schema.parse(rawArgs);
    const resourceId = tool.resourceId(args);
    const allowed = this.context.capabilities.some((capability) =>
      capability.action === tool.action &&
      capability.resourceId === resourceId &&
      capability.tenantId === this.context.tenantId &&
      capability.expiresAtMs > Date.now(),
    );
    if (!allowed) throw new Error("CAPABILITY_DENIED");
    this.#calls += 1;
    const remaining = this.context.deadlineMs - Date.now();
    return tool.run(args, AbortSignal.timeout(Math.min(remaining, 5_000)));
  }
}

const tools = {
  "attachment.read": {
    action: "attachment.read",
    schema: z.object({ attachmentId: z.string().uuid() }).strict(),
    resourceId: (args: { attachmentId: string }) => args.attachmentId,
    run: async ({ attachmentId }: { attachmentId: string }, signal: AbortSignal) =>
      readAttachmentById(attachmentId, signal),
  },
  "ticket.propose_update": {
    action: "ticket.propose_update",
    schema: z.object({
      ticketId: z.string().uuid(),
      patch: z.object({ title: z.string().min(1).max(200).optional() }).strict(),
    }).strict(),
    resourceId: (args: { ticketId: string }) => args.ticketId,
    run: async (args: unknown) => createToolIntent(args),
  },
} satisfies Record<string, Tool<any>>;
```

部署层最小 NetworkPolicy 示例：

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: agent-worker-egress
spec:
  podSelector:
    matchLabels:
      app: agent-worker
  policyTypes: [Ingress, Egress]
  ingress: []
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              name: controlled-egress
      ports:
        - protocol: TCP
          port: 8443
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
      ports:
        - protocol: UDP
          port: 53
```

容器还应设置非 root、只读根文件系统、删除 Linux capabilities、seccomp、临时空目录、CPU/内存/PID 上限，并使用工作负载身份而不是静态云 key。

验收：恶意文档能影响模型文本，但调用 `admin.export_secrets` 得到 `TOOL_DENIED`；任意路径参数无法通过 Schema；过期或跨租户 capability 被拒；第 13 次调用被预算阻断；运行日志中不存在测试 token；NetworkPolicy 实际阻止直接访问数据库和公网。

常见错误：只拒绝字符串 `localhost`、校验 DNS 后让 HTTP 客户端重新解析、自动跟随 redirect、相信 `Content-Length`、把容器当沙箱、让模型看到全量环境变量。

复写任务：从空文件重写 URL 验证顺序、bounded reader 和 ToolRunner；再画出应用校验、网络策略、工作负载身份三层防线。
