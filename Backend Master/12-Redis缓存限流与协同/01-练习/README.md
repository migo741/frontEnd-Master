# 第 12 章练习

## 练习一：不会回填旧权限的版本化缓存

实现 `getMembership(tenantId,userId)` cache-aside。PostgreSQL row 有单调 version；Redis value 有 schemaVersion/dataVersion/freshUntil/staleUntil。更新后删除/失效，慢读旧 version 不得覆盖新值。

要求：singleflight、TTL jitter、短负缓存、stale-while-revalidate、Redis 超时、DB 回源 bulkhead、Schema 解析与 tenant key。撤权是安全事件，禁止返回 stale allow。

测试至少覆盖：两个并发 miss、慢旧读与新写交错、缓存坏 JSON、Redis 清空、热 key 过期、随机不存在 id 穿透、撤权失效丢消息、跨 tenant key。

验收：用可控 barrier 构造竞态，不靠 sleep；最终缓存和数据库都保持最高 version；Redis 故障不会无限放大 DB 并发。

## 练习二：原子且租户公平的 token bucket

写 Redis 8 Lua 脚本，同时扣减 tenant bucket 与 principal bucket；任一个不足都不得扣另一个。使用 Redis TIME，支持 capacity、refill rate、cost、TTL，返回 allowed、remaining、retryAfterMs。

要求：key 使用同一 tenant hash tag 以便 Cluster 原子执行；参数验证；重复/并发请求不产生负 token；Redis 故障时登录/退款 fail closed，公共搜索使用受限本地 fallback。

验收：100 个并发 cost 请求恰好不超过预算；窗口边界无双倍突刺；一个用户耗尽个人额度不阻断其他用户，但 tenant 总额度仍有效；脚本不使用不确定本机时间。

## 复写任务

关掉答案，重写“只接受更高 dataVersion”的缓存 Lua 和双 bucket 脚本；解释为什么 TTL、Pub/Sub 删除、分布式锁都不能单独解决旧值回填。
