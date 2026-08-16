# 第 07 章答案

## 练习 1：零停机列替换

### 阶段 A：expand

迁移会话先设置有界等待；锁拿不到就失败退出，由发布系统重试：

```sql
BEGIN;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '30s';

ALTER TABLE app.ticket
  ADD COLUMN severity text,
  ALTER COLUMN priority DROP DEFAULT;
```

短期 compatibility trigger 让只写旧列的 V1 和只写新列的 V2 都保持一致。它是过渡设施，不是永久业务规则：

```sql
CREATE OR REPLACE FUNCTION app.sync_ticket_priority_severity()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  priority_changed boolean;
  severity_changed boolean;
BEGIN
  IF TG_OP = 'INSERT' THEN
    IF NEW.priority IS NULL AND NEW.severity IS NULL THEN
      -- 保留 V1 原本 DEFAULT 'normal' 的语义，同时避免 default 与 V3 的 severity 冲突。
      NEW.priority := 'normal';
      NEW.severity := 'normal';
      RETURN NEW;
    END IF;
    IF NEW.priority IS NOT NULL AND NEW.severity IS NOT NULL
       AND NEW.priority IS DISTINCT FROM NEW.severity THEN
      RAISE EXCEPTION 'priority/severity conflict' USING ERRCODE = '23514';
    END IF;
    NEW.priority := COALESCE(NEW.priority, NEW.severity);
    NEW.severity := COALESCE(NEW.severity, NEW.priority);
    RETURN NEW;
  END IF;

  priority_changed := NEW.priority IS DISTINCT FROM OLD.priority;
  severity_changed := NEW.severity IS DISTINCT FROM OLD.severity;
  IF priority_changed AND severity_changed
     AND NEW.priority IS DISTINCT FROM NEW.severity THEN
    RAISE EXCEPTION 'priority/severity conflict' USING ERRCODE = '23514';
  ELSIF priority_changed AND NOT severity_changed THEN
    NEW.severity := NEW.priority;
  ELSIF severity_changed AND NOT priority_changed THEN
    NEW.priority := NEW.severity;
  END IF;
  RETURN NEW;
END
$$;

CREATE TRIGGER ticket_priority_severity_compat_trg
BEFORE INSERT OR UPDATE OF priority, severity ON app.ticket
FOR EACH ROW EXECUTE FUNCTION app.sync_ticket_priority_severity();

COMMIT;
```

`ADD COLUMN`、移除旧 default 与安装 trigger 必须在同一事务提交；任一步失败都会整体回滚，线上不会看见“旧 default 已消失但 trigger 尚未安装”的中间状态。

V2 首个版本读取 `COALESCE(severity, priority)`，写入两列相同值。trigger 继续保护未升级 V1。若双列显式冲突，SQLSTATE `23514` 触发内部告警，不能悄悄选一边。

### 阶段 B：可重入 backfill

每次事务只处理一批；worker 循环执行到 `rowCount = 0`，根据 replica lag 节流：

```sql
WITH batch AS (
  SELECT tenant_id, id
  FROM app.ticket
  WHERE severity IS NULL
  ORDER BY tenant_id, id
  LIMIT 1000
  FOR UPDATE SKIP LOCKED
)
UPDATE app.ticket AS ticket
SET severity = ticket.priority
FROM batch
WHERE ticket.tenant_id = batch.tenant_id
  AND ticket.id = batch.id
  AND ticket.severity IS NULL
RETURNING ticket.tenant_id, ticket.id;
```

进度与差异查询：

```sql
SELECT count(*) FILTER (WHERE severity IS NULL) AS remaining,
       count(*) FILTER (WHERE severity IS DISTINCT FROM priority) AS divergent
FROM app.ticket;
```

### 阶段 C：验证约束

```sql
ALTER TABLE app.ticket
  ADD CONSTRAINT ticket_severity_value_ck
  CHECK (severity IN ('low', 'normal', 'high', 'urgent')) NOT VALID,
  ADD CONSTRAINT ticket_priority_severity_equal_ck
  CHECK (priority IS NOT DISTINCT FROM severity) NOT VALID,
  ADD CONSTRAINT ticket_severity_present_ck
  CHECK (severity IS NOT NULL) NOT VALID;

ALTER TABLE app.ticket VALIDATE CONSTRAINT ticket_severity_value_ck;
ALTER TABLE app.ticket VALIDATE CONSTRAINT ticket_priority_severity_equal_ck;
ALTER TABLE app.ticket VALIDATE CONSTRAINT ticket_severity_present_ck;

SET lock_timeout = '2s';
ALTER TABLE app.ticket ALTER COLUMN severity SET NOT NULL;
```

验证期间继续观察锁、WAL、replica lag 与 divergence。约束有效不代表所有 reader 已升级。

### 阶段 D：cutover 与 contract

部署 V2：读 severity，兼容期仍双写。随后部署 V3：只读写 severity；过渡 trigger 会继续为仍存在的 priority 补值。等待：

- V1 实例、worker、CLI 全部归零；
- 旧列读写 telemetry 持续一个完整业务周期为零；
- `remaining = 0`、`divergent = 0`；
- 恢复演练和应用回滚演练通过；
- CDC、报表和 Python worker 均已迁移。

随后单独发布 contract：

```sql
BEGIN;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '30s';
ALTER TABLE app.ticket ALTER COLUMN severity SET DEFAULT 'normal';
DROP TRIGGER ticket_priority_severity_compat_trg ON app.ticket;
DROP FUNCTION app.sync_ticket_priority_severity();
ALTER TABLE app.ticket DROP CONSTRAINT ticket_priority_severity_equal_ck;
ALTER TABLE app.ticket DROP COLUMN priority;
COMMIT;
```

先部署不再引用 priority 的 V3，再执行上述 SQL。expand 时移除 priority default、改由 trigger 提供默认值，正是为了让 V1 省略 priority 和 V3 只写 severity 都能工作。若 contract 前应用需回滚，回滚到 V1/V2 都有旧列；contract 后不能再回滚 V1，应 roll forward 或从恢复点提取数据。

### 混跑测试与常见错误

集成测试顺序：V1 insert → V2 read；V2 update severity → V1 read priority；并发 V1/V2 更新同一行时用第 02/06 章的 ETag/version 控制；显式冲突双写应 `23514`；backfill 重跑两次结果相同。

trigger 会增加写成本且隐藏迁移逻辑，所以必须有删除日期。常见错误是 V2 只写 severity 却无 compatibility、全表单事务回填、在同一 migration 创建 concurrent index，或 contract 只凭代码搜索。

### 复写任务

把值域改为新旧不等价映射，例如 `urgent → critical`；设计映射表、无法映射行的隔离队列和双向兼容边界，不能在 trigger 中悄悄丢语义。

## 练习 2：隔离恢复演练

### 目标与备份清单

示例目标：演练环境 RTO 30 分钟；此次逻辑 dump 的 RPO 是 dump snapshot 时刻，不能恢复之后写入，因此不满足生产 5 分钟 RPO。生产要用受监控的 base backup + 连续 WAL 或云 PITR。

清单至少记录：UTC 开始/完成时间、源实例标识、PostgreSQL 版本、migration ledger 最大 ID、dump SHA-256、工具版本、加密位置和负责人。

### 可复制的本地演练

以下只针对一次性本地 Compose 环境，restore 目标必须是新数据库：

```bash
mkdir -p ./restore-artifacts
docker compose exec -T db \
  pg_dump -U postgres -d backend --format=custom --no-owner \
  > ./restore-artifacts/backend.dump

shasum -a 256 ./restore-artifacts/backend.dump \
  > ./restore-artifacts/backend.dump.sha256
shasum -a 256 -c ./restore-artifacts/backend.dump.sha256

docker compose exec -T db \
  createdb -U postgres backend_restore
docker compose exec -T db \
  pg_restore -U postgres -d backend_restore --exit-on-error --no-owner \
  < ./restore-artifacts/backend.dump
```

不要在共享或生产实例照抄固定 `backend_restore` 名称；演练系统应生成唯一目标、限制网络访问并在审批后销毁。

### 数据验证 SQL

```sql
-- 在 backend_restore 上执行
SELECT max(id) AS latest_migration FROM app.schema_migration;

SELECT 'tenant' AS relation, count(*) FROM app.tenant
UNION ALL SELECT 'account', count(*) FROM app.account
UNION ALL SELECT 'ticket', count(*) FROM app.ticket;

SELECT count(*) AS orphan_requesters
FROM app.ticket t
LEFT JOIN app.account a
  ON a.tenant_id = t.tenant_id AND a.id = t.requester_id
WHERE a.id IS NULL;

SELECT count(*) AS invalid_ticket_rows
FROM app.ticket
WHERE status NOT IN ('open', 'in_progress', 'resolved', 'closed')
   OR updated_at < created_at;

SELECT min(created_at), max(created_at), count(*)
FROM app.ticket;
```

此外用只读应用凭证启动 smoke test：每个 tenant 只能看自己数据，关键列表 plan 可用，最近已知 marker 存在。任何一项失败都禁止切流。

### PITR runbook 骨架

1. 停止继续执行错误 migration，记录首次错误时间、当前 LSN 和负责人。
2. 选择误操作之前的 target time/restore point，在隔离实例恢复 base backup 与 WAL。
3. 验证 WAL 连续、recovery target reached，并记录新 timeline。
4. 执行相同完整性、RLS、应用 smoke 与差异查询。
5. 对恢复点之后的合法写入建立差异清单：从审计/outbox/旧库只读副本重放或人工补偿。
6. 经事故指挥批准后切换连接，保留旧库只读，持续核对。

### 失败语义、常见错误与复写

dump checksum 正确只证明文件未变化，不证明内容可恢复；`pg_restore --list` 也不能替代真实 restore。RTO 必须从开始处置到应用可用，而不是只算 `pg_restore` 命令时间。

常见错误：恢复覆盖源库、恢复后直接切流、忽略角色/扩展/外部对象、未验证租户隔离、演练数据长期留在低权限环境，或把“每天有备份”写成恢复证据。

复写：截断 dump 或让 restore 缺少一个 migration，确保 `--exit-on-error` 与 schema gate 阻止 smoke；记录告警到定位所耗时间并更新 runbook。
