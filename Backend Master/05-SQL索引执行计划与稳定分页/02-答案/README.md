# 第 05 章答案

## 练习 1：访问模式与索引证据

### 查询与索引

```sql
-- 路径 A：指定一个 status
SELECT id, title, status, priority, created_at
FROM app.ticket
WHERE tenant_id = $1::uuid
  AND status = $2::text
ORDER BY created_at DESC, id DESC
LIMIT 51;

CREATE INDEX ticket_tenant_status_feed_idx
ON app.ticket (tenant_id, status, created_at DESC, id DESC)
INCLUDE (title, priority);

-- 路径 B：不筛 status
SELECT id, title, status, priority, created_at
FROM app.ticket
WHERE tenant_id = $1::uuid
ORDER BY created_at DESC, id DESC
LIMIT 51;

CREATE INDEX ticket_tenant_feed_idx
ON app.ticket (tenant_id, created_at DESC, id DESC)
INCLUDE (title, status, priority);
```

先 `ANALYZE app.ticket`，再对代表性大/小租户分别执行：

```sql
EXPLAIN (ANALYZE, BUFFERS, WAL, FORMAT JSON)
SELECT id, title, status, priority, created_at
FROM app.ticket
WHERE tenant_id = '00000000-0000-4000-8000-000000000001'::uuid
  AND status = 'open'
ORDER BY created_at DESC, id DESC
LIMIT 51;
```

### 怎样读结果

理想证据不是固定节点名，而是：扫描接近 51 行即可结束、没有大规模显式 Sort、Rows Removed 很小、buffer 访问随页大小而不是租户总量增长。刚写入的数据 visibility map 未完善时，Index Only Scan 仍可能有 heap fetch，这是正常现象。

为数据倾斜保存大租户与小租户两份 plan。若 estimated rows 与 actual rows 相差几个数量级，先更新统计；必要时对 `(tenant_id, status)` 建 extended statistics：

```sql
CREATE STATISTICS ticket_tenant_status_stats (dependencies, mcv)
ON tenant_id, status FROM app.ticket;
ANALYZE app.ticket;
```

### 写入代价与常见错误

两个 feed index 会放大每次工单写入，且 INCLUDE title 会随标题更新产生更多索引写。应以查询频率和 P95 证明保留。不要额外创建与复合索引左前缀重复的 `tenant_id` 单列索引，除非有独立证据。

常见错误：只在 status 建索引、把列 cast 成 text、用随机小数据测、只看 planning cost、或断言“任何 Seq Scan 都坏”。

### 复写任务

增加只看 active 工单的真实高频路径，比较完整索引与 partial index 的大小、写放大和计划；改变 active 占比后重新测量。

## 练习 2：签名 keyset cursor

### Cursor codec

```ts
// cursor.ts
import { createHmac, timingSafeEqual } from "node:crypto";

export type Status = "open" | "in_progress" | "resolved" | "closed";
type Payload = { v: 1; status: Status | null; createdAt: string; id: string };
const statuses = new Set<Status>(["open", "in_progress", "resolved", "closed"]);
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export class InvalidCursor extends Error {
  readonly code = "INVALID_CURSOR";
  constructor() { super("cursor is invalid"); }
}

export function createCursorCodec(key: Buffer) {
  if (key.length < 32) throw new TypeError("cursor HMAC key must be at least 32 bytes");
  const sign = (data: string) => createHmac("sha256", key).update(data).digest();

  function encode(payload: Payload): string {
    const data = Buffer.from(JSON.stringify(payload)).toString("base64url");
    return `${data}.${sign(data).toString("base64url")}`;
  }

  function decode(token: string, expectedStatus: Status | null): Payload {
    try {
      if (token.length > 1024) throw new Error("long");
      const parts = token.split(".");
      if (parts.length !== 2) throw new Error("shape");
      const [data, rawSignature] = parts as [string, string];
      const supplied = Buffer.from(rawSignature, "base64url");
      const expected = sign(data);
      if (supplied.length !== expected.length || !timingSafeEqual(supplied, expected)) {
        throw new Error("signature");
      }
      const value: unknown = JSON.parse(Buffer.from(data, "base64url").toString("utf8"));
      if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("payload");
      const row = value as Record<string, unknown>;
      if (Object.keys(row).sort().join(",") !== "createdAt,id,status,v") throw new Error("keys");
      if (row.v !== 1 || row.status !== expectedStatus) throw new Error("version/filter");
      if (row.status !== null && (typeof row.status !== "string" || !statuses.has(row.status as Status))) {
        throw new Error("status");
      }
      if (typeof row.createdAt !== "string") throw new Error("time");
      const date = new Date(row.createdAt);
      if (Number.isNaN(date.getTime()) || date.toISOString() !== row.createdAt) throw new Error("time");
      if (typeof row.id !== "string" || !uuid.test(row.id)) throw new Error("id");
      return row as Payload;
    } catch {
      throw new InvalidCursor();
    }
  }

  return { encode, decode };
}
```

### 查询实现

```ts
// list-tickets.ts
import type { Pool } from "pg";
import type { Status, createCursorCodec } from "./cursor.js";

type Row = { id: string; title: string; status: Status; priority: string; created_at: Date };

type CursorCodec = ReturnType<typeof createCursorCodec>;

export function createListTickets(pool: Pool, codec: CursorCodec) {
  return async (input: {
    tenantId: string; status: Status | null; limit: number; after?: string;
  }) => {
    if (!Number.isInteger(input.limit) || input.limit < 1 || input.limit > 100) {
      throw new TypeError("limit must be 1..100");
    }
    const after = input.after ? codec.decode(input.after, input.status) : undefined;
    const values: unknown[] = [input.tenantId];
    const predicates = ["tenant_id = $1::uuid"];
    if (input.status !== null) {
      values.push(input.status);
      predicates.push(`status = $${values.length}::text`);
    }
    if (after) {
      values.push(after.createdAt, after.id);
      predicates.push(`(created_at, id) < ($${values.length - 1}::timestamptz, $${values.length}::uuid)`);
    }
    values.push(input.limit + 1);
    const sql = `
      SELECT id, title, status, priority, created_at
      FROM app.ticket
      WHERE ${predicates.join(" AND ")}
      ORDER BY created_at DESC, id DESC
      LIMIT $${values.length}::int`;
    const result = await pool.query<Row>(sql, values);
    const hasMore = result.rows.length > input.limit;
    const items = result.rows.slice(0, input.limit);
    const last = items.at(-1);
    const next = hasMore && last ? codec.encode({
      v: 1, status: input.status,
      createdAt: last.created_at.toISOString(), id: last.id,
    }) : null;
    return { items, next };
  };
}
```

代码动态构造的只有内部固定 SQL 片段；所有外部值仍参数化。也可以维护两个完全静态 SQL 常量，便于查询审计。

### 验收与并发语义

测试种入同一 `created_at` 的数百 UUID，逐页收集 ID，断言集合大小等于数组长度。第一页后插入一条更晚记录，它不会挤入第二页，也不会让旧记录重复；重新从第一页查询才能看见它。

删除尚未遍历的记录会让它缺席，状态变化会移入/移出过滤集合；协议不提供跨请求 snapshot。`created_at` 必须不可变，否则行可能跨越 cursor。

常见错误是 `>=` 造成重复、cursor 指向第 51 条而漏掉它、只按时间排序、把 tenant 放进可伪造 cursor，或先解码 JSON 再验证签名。

### 复写任务

为 cursor 增加 key ID 和双 key 验证，实现无中断 HMAC 轮换；旧 key 只能验证，所有新 cursor 用 active key 签发。
