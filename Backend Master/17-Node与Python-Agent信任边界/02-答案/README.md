# 第 17 章答案

## 练习一答案：可演进的 Node ↔ Python Agent 契约

TypeScript 侧用 Zod 把队列消息重新降级为 `unknown` 后验证：

```ts
import { z } from "zod";

const ResourceCapability = z.object({
  action: z.enum(["kb.read", "ticket.suggest", "attachment.read"]),
  resourceId: z.string().min(1).max(128),
  expiresAt: z.string().datetime({ offset: true }),
  maxUses: z.number().int().positive().max(100),
}).strict();

export const AgentJobV1 = z.object({
  schemaVersion: z.literal(1),
  messageId: z.string().uuid(),
  runId: z.string().uuid(),
  tenantId: z.string().uuid(),
  attempt: z.number().int().min(1).max(10),
  deadline: z.string().datetime({ offset: true }),
  inputRef: z.string().min(1).max(512),
  inputSha256: z.string().regex(/^[a-f0-9]{64}$/),
  capabilities: z.array(ResourceCapability).max(20),
  traceparent: z.string().regex(/^00-[a-f0-9]{32}-[a-f0-9]{16}-0[01]$/).optional(),
}).strict();

const Usage = z.object({
  inputTokens: z.number().int().nonnegative(),
  outputTokens: z.number().int().nonnegative(),
  model: z.string().min(1).max(100),
}).strict();

export const AgentResultV1 = z.discriminatedUnion("kind", [
  z.object({
    schemaVersion: z.literal(1),
    messageId: z.string().uuid(),
    runId: z.string().uuid(),
    kind: z.literal("completed"),
    result: z.record(z.string(), z.unknown()),
    checkpoint: z.record(z.string(), z.unknown()),
    usage: Usage,
  }).strict(),
  z.object({
    schemaVersion: z.literal(1),
    messageId: z.string().uuid(),
    runId: z.string().uuid(),
    kind: z.literal("tool_intent"),
    intentId: z.string().uuid(),
    tool: z.enum(["ticket.close", "notification.send"]),
    args: z.record(z.string(), z.unknown()),
  }).strict(),
  z.object({
    schemaVersion: z.literal(1),
    messageId: z.string().uuid(),
    runId: z.string().uuid(),
    kind: z.literal("retryable_error"),
    code: z.enum(["MODEL_RATE_LIMIT", "MODEL_TIMEOUT", "DEPENDENCY_UNAVAILABLE"]),
    retryAfterMs: z.number().int().min(100).max(60_000),
  }).strict(),
  z.object({
    schemaVersion: z.literal(1),
    messageId: z.string().uuid(),
    runId: z.string().uuid(),
    kind: z.literal("permanent_error"),
    code: z.enum(["INVALID_INPUT", "POLICY_REJECTED", "UNSUPPORTED_VERSION"]),
  }).strict(),
  z.object({
    schemaVersion: z.literal(1),
    messageId: z.string().uuid(),
    runId: z.string().uuid(),
    kind: z.literal("cancelled"),
    checkpoint: z.record(z.string(), z.unknown()),
  }).strict(),
]);

export function parseAgentResult(raw: unknown) {
  return AgentResultV1.parse(raw);
}
```

Python 使用同样的封闭联合：

```py
from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

class Capability(ClosedModel):
    action: Literal["kb.read", "ticket.suggest", "attachment.read"]
    resourceId: str = Field(min_length=1, max_length=128)
    expiresAt: datetime
    maxUses: int = Field(gt=0, le=100)

class AgentJobV1(ClosedModel):
    schemaVersion: Literal[1]
    messageId: UUID
    runId: UUID
    tenantId: UUID
    attempt: int = Field(ge=1, le=10)
    deadline: datetime
    inputRef: str = Field(min_length=1, max_length=512)
    inputSha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    capabilities: list[Capability] = Field(max_length=20)
    traceparent: str | None = Field(
        default=None,
        pattern=r"^00-[a-f0-9]{32}-[a-f0-9]{16}-0[01]$",
    )

    @field_validator("deadline")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("deadline must include timezone")
        return value

    def assert_not_expired(self) -> None:
        if self.deadline <= datetime.now(timezone.utc):
            raise TimeoutError("job deadline exceeded")

class Completed(ClosedModel):
    schemaVersion: Literal[1]
    messageId: UUID
    runId: UUID
    kind: Literal["completed"]
    result: dict[str, object]
    checkpoint: dict[str, object]
    usage: dict[str, object]

class ToolIntent(ClosedModel):
    schemaVersion: Literal[1]
    messageId: UUID
    runId: UUID
    kind: Literal["tool_intent"]
    intentId: UUID
    tool: Literal["ticket.close", "notification.send"]
    args: dict[str, object]

class RetryableError(ClosedModel):
    schemaVersion: Literal[1]
    messageId: UUID
    runId: UUID
    kind: Literal["retryable_error"]
    code: Literal["MODEL_RATE_LIMIT", "MODEL_TIMEOUT", "DEPENDENCY_UNAVAILABLE"]
    retryAfterMs: int = Field(ge=100, le=60_000)

class PermanentError(ClosedModel):
    schemaVersion: Literal[1]
    messageId: UUID
    runId: UUID
    kind: Literal["permanent_error"]
    code: Literal["INVALID_INPUT", "POLICY_REJECTED", "UNSUPPORTED_VERSION"]

class Cancelled(ClosedModel):
    schemaVersion: Literal[1]
    messageId: UUID
    runId: UUID
    kind: Literal["cancelled"]
    checkpoint: dict[str, object]

AgentResultV1 = Annotated[
    Completed | ToolIntent | RetryableError | PermanentError | Cancelled,
    Field(discriminator="kind"),
]
```

共享 fixture 目录：

```text
contracts/agent/v1/
├── valid-job-minimal.json
├── valid-job-capabilities.json
├── valid-result-completed.json
├── valid-result-intent.json
├── invalid-extra-field.json
├── invalid-naive-deadline.json
├── invalid-capability.json
└── invalid-version.json
```

Node 测试读取所有 fixture 调 `safeParse`，Python 用 `pytest.mark.parametrize` 调 `model_validate_json`。CI 必须同时运行；只比较生成 Schema 不足以发现默认值和时间解析差异。

失败语义：未知版本进 quarantine；payload 非法记稳定错误码与 hash，不打印正文；deadline 已过直接返回 cancelled/permanent 结果，不调用模型；对象 hash 不符按安全事件处理。

## 练习二答案：参数绑定的 Tool Intent 与 HITL

表结构把内容、审批与执行分开：

```sql
create table tool_intents (
  id uuid primary key,
  tenant_id uuid not null,
  run_id uuid not null,
  tool text not null,
  args jsonb not null,
  args_hash text not null,
  status text not null check (status in (
    'awaiting_approval','approved','rejected','expired',
    'executing','succeeded','failed_retryable','failed_permanent'
  )),
  expires_at timestamptz not null,
  approved_by uuid,
  approved_at timestamptz,
  lease_owner text,
  lease_until timestamptz,
  result jsonb,
  created_at timestamptz not null default now(),
  unique (tenant_id, run_id, id)
);
```

只规范化 JSON 值：

```ts
import { createHash } from "node:crypto";

type Json = null | boolean | number | string | Json[] | { [key: string]: Json };

function canonical(value: Json): string {
  if (typeof value === "number" && !Number.isFinite(value)) {
    throw new Error("NON_FINITE_JSON_NUMBER");
  }
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  const entries = Object.entries(value).sort(([a], [b]) =>
    a < b ? -1 : a > b ? 1 : 0,
  );
  return `{${entries.map(([k, v]) => `${JSON.stringify(k)}:${canonical(v)}`).join(",")}}`;
}

export function argsHash(value: Json): string {
  return createHash("sha256").update(canonical(value), "utf8").digest("hex");
}
```

执行 lease 必须是数据库条件更新：

```sql
update tool_intents
set status = 'executing',
    lease_owner = $4,
    lease_until = now() + interval '30 seconds'
where tenant_id = $1
  and id = $2
  and args_hash = $3
  and status = 'approved'
  and expires_at > now()
returning *;
```

核心执行函数：

```ts
type ToolExecutor = (input: {
  idempotencyKey: string;
  tenantId: string;
  args: Json;
  signal: AbortSignal;
}) => Promise<Json>;

export async function executeApprovedIntent(input: {
  tenantId: string;
  intentId: string;
  expectedHash: string;
  workerId: string;
  authorizeAgain: (intent: unknown) => Promise<boolean>;
  claim: () => Promise<null | { id: string; args: Json; argsHash: string }>;
  executor: ToolExecutor;
  complete: (result: Json) => Promise<void>;
  fail: (error: unknown) => Promise<void>;
  signal: AbortSignal;
}) {
  const intent = await input.claim();
  if (!intent) return { kind: "not_claimed" } as const;
  if (argsHash(intent.args) !== intent.argsHash || intent.argsHash !== input.expectedHash) {
    await input.fail(new Error("ARGS_HASH_MISMATCH"));
    return { kind: "rejected" } as const;
  }
  if (!(await input.authorizeAgain(intent))) {
    await input.fail(new Error("AUTHORIZATION_CHANGED"));
    return { kind: "rejected" } as const;
  }
  try {
    const result = await input.executor({
      idempotencyKey: intent.id,
      tenantId: input.tenantId,
      args: intent.args,
      signal: input.signal,
    });
    await input.complete(result);
    return { kind: "succeeded", result } as const;
  } catch (error) {
    await input.fail(error);
    throw error;
  }
}
```

外部供应商若不支持幂等键，不能声称 exactly-once。应建立本地 execution record、查询供应商结果并提供人工对账/补偿路径。

验收：参数改一个空格或资源 ID 后旧审批不可用；成员移除后执行被拒；两个 worker 只有一个 claim 成功；外部执行成功后本地进程崩溃，再跑时通过相同 idempotency key 得到原结果；审计能还原提案、批准、执行与失败。

常见错误：把用户 JWT 传给 worker、Python 直连主库、仅按工具名审批、批准后不重新授权、把 args hash 当授权、日志打印完整 Prompt 和工具参数。

复写任务：不看答案，重新写封闭协议、共享 fixture、canonical hash 与原子 claim，并说明四处信任边界。
