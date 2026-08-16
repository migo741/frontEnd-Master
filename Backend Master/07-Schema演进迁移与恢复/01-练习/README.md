# 第 07 章练习

## 练习 1（经典必做）：priority → severity 零停机演进

当前 V1 只读写 `ticket.priority NOT NULL`；V2 要改为 `severity`，两列值域相同。设计完整 expand/migrate/contract：

- 滚动发布期间 V1、V2 可任意混跑。
- 新旧列不能长期分叉；冲突双写必须拒绝并报警。
- 历史数据分批回填，可并行、暂停、崩溃重跑。
- 用 `NOT VALID → VALIDATE` 建立一致性证据，再设置新列 NOT NULL。
- contract 只有旧版本归零、旧列使用指标归零、恢复演练通过后才能执行。
- 每步写 lock/statement timeout、失败清理和回滚应用策略。

交付 SQL、V1/V2 混跑兼容测试、backfill 进度查询和 contract checklist。不得一次 rename 或单事务全表 UPDATE。

## 练习 2（生产事故）：证明备份可以恢复

为 PostgreSQL 18 设计并实际执行一次隔离恢复演练：

1. 定义目标 RPO/RTO 和此次逻辑备份能满足/不能满足什么。
2. 生成 custom-format backup、checksum 和元数据清单。
3. 模拟错误迁移或误删；严禁把 restore 覆盖回源库。
4. 恢复到新数据库，运行 migration ledger、行数、孤儿、跨租户、时间范围和应用 smoke checks。
5. 记录实际耗时、最后恢复时间点、失败步骤与清理方式。
6. 写出升级到 base backup + WAL/PITR 后的恢复 runbook，并解释恢复点后的合法写入如何对账。

复写时让备份文件损坏或故意缺一个 migration，证明验证门会阻止切流。
