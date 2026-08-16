# 第 04 章答案

## 练习 1：关系模型与约束

### 可执行 DDL

```sql
CREATE SCHEMA IF NOT EXISTS app;

CREATE TABLE app.tenant (
  id          uuid        NOT NULL,
  slug        text        NOT NULL,
  name        text        NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT tenant_pk PRIMARY KEY (id),
  CONSTRAINT tenant_slug_uk UNIQUE (slug),
  CONSTRAINT tenant_slug_shape_ck CHECK (slug ~ '^[a-z0-9][a-z0-9-]{1,62}$'),
  CONSTRAINT tenant_name_nonempty_ck CHECK (btrim(name) <> '')
);

CREATE TABLE app.account (
  tenant_id        uuid        NOT NULL,
  id               uuid        NOT NULL,
  normalized_email text        NOT NULL,
  display_name     text        NOT NULL,
  created_at       timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT account_pk PRIMARY KEY (tenant_id, id),
  CONSTRAINT account_tenant_fk FOREIGN KEY (tenant_id)
    REFERENCES app.tenant (id) ON DELETE RESTRICT,
  CONSTRAINT account_tenant_email_uk UNIQUE (tenant_id, normalized_email),
  CONSTRAINT account_email_normalized_ck CHECK (
    normalized_email = lower(btrim(normalized_email))
    AND normalized_email LIKE '%@%'
  ),
  CONSTRAINT account_display_name_nonempty_ck CHECK (btrim(display_name) <> '')
);

CREATE TABLE app.ticket (
  tenant_id    uuid        NOT NULL,
  id           uuid        NOT NULL,
  requester_id uuid        NOT NULL,
  created_by   uuid        NOT NULL,
  title        text        NOT NULL,
  status       text        NOT NULL DEFAULT 'open',
  priority     text        NOT NULL DEFAULT 'normal',
  created_at   timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at   timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT ticket_pk PRIMARY KEY (tenant_id, id),
  CONSTRAINT ticket_tenant_fk FOREIGN KEY (tenant_id)
    REFERENCES app.tenant (id) ON DELETE RESTRICT,
  CONSTRAINT ticket_requester_same_tenant_fk FOREIGN KEY (tenant_id, requester_id)
    REFERENCES app.account (tenant_id, id) ON DELETE RESTRICT,
  CONSTRAINT ticket_creator_same_tenant_fk FOREIGN KEY (tenant_id, created_by)
    REFERENCES app.account (tenant_id, id) ON DELETE RESTRICT,
  CONSTRAINT ticket_title_nonempty_ck CHECK (btrim(title) <> ''),
  CONSTRAINT ticket_status_ck CHECK (
    status IN ('open', 'in_progress', 'resolved', 'closed')
  ),
  CONSTRAINT ticket_priority_ck CHECK (
    priority IN ('low', 'normal', 'high', 'urgent')
  ),
  CONSTRAINT ticket_time_order_ck CHECK (updated_at >= created_at)
);

-- 主键已覆盖以 tenant_id 开头的账户查找；以下索引服务工单反向外键检查与列表。
CREATE INDEX ticket_requester_idx ON app.ticket (tenant_id, requester_id);
CREATE INDEX ticket_creator_idx ON app.ticket (tenant_id, created_by);
CREATE INDEX ticket_list_idx ON app.ticket (tenant_id, created_at DESC, id DESC);
```

### 违法测试样例

```sql
-- 测试 fixture 中先创建 tenant A/B 和各自账户。
-- 同 tenant 重复 normalized_email → 23505 / account_tenant_email_uk
-- 跨 tenant 相同 email → 成功

INSERT INTO app.ticket (
  tenant_id, id, requester_id, created_by, title
) VALUES (
  :'tenant_a', :'ticket_1', :'account_b', :'account_a', 'must fail'
);
-- 23503 / ticket_requester_same_tenant_fk

INSERT INTO app.ticket (
  tenant_id, id, requester_id, created_by, title, status
) VALUES (
  :'tenant_a', :'ticket_2', :'account_a', :'account_a', 'bad', 'deleted'
);
-- 23514 / ticket_status_ck

INSERT INTO app.ticket (
  tenant_id, id, requester_id, created_by, title, created_at, updated_at
) VALUES (
  :'tenant_a', :'ticket_3', :'account_a', :'account_a', 'bad time', now(), now() - interval '1 hour'
);
-- 23514 / ticket_time_order_ck
```

Node 测试捕获 `pg` 错误时断言 `code` 与 `constraint`：

```ts
await assert.rejects(insertCrossTenant(), (error: unknown) => {
  const value = error as { code?: string; constraint?: string };
  assert.equal(value.code, "23503");
  assert.equal(value.constraint, "ticket_requester_same_tenant_fk");
  return true;
});
```

### 设计边界与常见错误

邮箱这里只演示规范形态，不声称实现完整邮件标准；真正规范规则由产品契约决定。tenant 物理删除使用 `RESTRICT`，避免同步级联删除全部业务事实。以后若支持归档，应建状态和审计流程。

常见错误是只让 `account.id` 全局唯一后建立单列外键——它能找到账号，却不能从键上证明 tenant 相同；或依赖 ORM relation 而没有数据库 FK。

### 复写任务

加入 `ticket_comment`，要求 author、ticket、comment 三者同租户；只用键与外键证明，不写 trigger。

## 练习 2：RLS 默认拒绝

### 角色、context 与 policy

以下脚本由迁移 owner 执行；密码通过部署秘密系统创建，不写入仓库。

```sql
-- 认证方式/密码由部署秘密系统配置；也可把 LOGIN 与权限角色再拆开。
CREATE ROLE app_runtime LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;

CREATE OR REPLACE FUNCTION app.current_tenant_id()
RETURNS uuid
LANGUAGE sql
STABLE
SET search_path = pg_catalog
AS $$
  SELECT NULLIF(current_setting('app.tenant_id', true), '')::uuid
$$;

REVOKE ALL ON SCHEMA app FROM PUBLIC;
REVOKE ALL ON FUNCTION app.current_tenant_id() FROM PUBLIC;
GRANT USAGE ON SCHEMA app TO app_runtime;
GRANT EXECUTE ON FUNCTION app.current_tenant_id() TO app_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON app.account, app.ticket TO app_runtime;
GRANT SELECT ON app.tenant TO app_runtime;

ALTER TABLE app.tenant ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.account ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.ticket ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.tenant FORCE ROW LEVEL SECURITY;
ALTER TABLE app.account FORCE ROW LEVEL SECURITY;
ALTER TABLE app.ticket FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON app.tenant
  USING (id = app.current_tenant_id())
  WITH CHECK (id = app.current_tenant_id());

CREATE POLICY account_tenant_isolation ON app.account
  USING (tenant_id = app.current_tenant_id())
  WITH CHECK (tenant_id = app.current_tenant_id());

CREATE POLICY ticket_tenant_isolation ON app.ticket
  USING (tenant_id = app.current_tenant_id())
  WITH CHECK (tenant_id = app.current_tenant_id());
```

生产中通常不给 `app_runtime` 创建 tenant 的权限；tenant onboarding 走更窄的管理用例。这里 tenant policy 只完整展示读写语义。

### 事务局部上下文

```ts
import type { Pool, PoolClient } from "pg";

export async function withTenant<T>(
  pool: Pool,
  tenantId: string,
  operation: (client: PoolClient) => Promise<T>,
): Promise<T> {
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    await client.query("SELECT set_config('app.tenant_id', $1, true)", [tenantId]);
    const value = await operation(client);
    await client.query("COMMIT");
    return value;
  } catch (error) {
    await client.query("ROLLBACK").catch(() => undefined);
    throw error;
  } finally {
    client.release();
  }
}
```

### 攻击型集成测试

```ts
test("tenant context filters reads and writes", async () => {
  const aRows = await withTenant(appPool, tenantA, async (db) =>
    db.query("SELECT tenant_id, id FROM app.ticket ORDER BY id"));
  assert(aRows.rows.every((row) => row.tenant_id === tenantA));

  await assert.rejects(
    withTenant(appPool, tenantA, (db) => db.query(
      `INSERT INTO app.ticket
       (tenant_id, id, requester_id, created_by, title)
       VALUES ($1, $2, $3, $3, 'spoof')`,
      [tenantB, crypto.randomUUID(), accountB],
    )),
    (error: unknown) => {
      assert.equal((error as { code?: string }).code, "42501");
      return true;
    },
  );
});

test("missing context is deny by default and local setting does not leak", async () => {
  const first = await appPool.query("SELECT * FROM app.ticket");
  assert.equal(first.rowCount, 0);

  await withTenant(appPool, tenantA, (db) => db.query("SELECT 1"));
  const after = await appPool.query("SELECT current_setting('app.tenant_id', true) AS tenant");
  assert([null, ""].includes(after.rows[0].tenant));
});
```

### 失败语义、验收与复写

查询缺 context 返回空集，写入触发 RLS 拒绝；应用应把这视为内部上下文缺陷，而不是假装资源不存在。认证 adapter 必须先得到可信 tenant，再进入 `withTenant`。后台任务同样从经过验证的 envelope 建 context。

常见错误是用 session 级 `SET`、把迁移 owner 连接池给应用、忘记 `WITH CHECK`，或测试只用表 owner 因而误以为 policy 生效。普通运行时角色本身可以修改自定义 GUC，所以这套 RLS 主要防止查询漏写 tenant，并不能抵抗任意 SQL 注入或已被完全控制的数据库凭证；第 09 章会继续收紧授权边界。

复写：为独立 support role 设计只读、限时、带工单号的跨租户访问；写审计触发器并证明普通 app role 无法伪造 actor。
