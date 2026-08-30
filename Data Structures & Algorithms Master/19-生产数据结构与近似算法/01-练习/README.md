# 第 19 章练习

## 练习 1：LRU + TTL 的有界缓存（经典组合）

```ts
type EvictionReason = "capacity" | "expired" | "deleted";

declare class LruTtlCache<K, V> {
  constructor(options: {
    maxEntries: number;
    now: () => number;
    onEvict?: (key: K, value: V, reason: EvictionReason) => void;
  });
  get size(): number;
  get(key: K): V | undefined;
  has(key: K): boolean;
  set(key: K, value: V, ttlMs: number): boolean;
  delete(key: K): boolean;
}
```

Map + 双链维护 LRU，min-heap + generation 维护 TTL。`expiresAt<=now` 视为过期；每个公共操作先 purge。get/has 命中是否刷新 recency：本题都刷新，但不延长 TTL。update 替换 value/TTL 并刷新 recency。maxEntries=0 时不保存。onEvict 异常必须隔离，不破坏结构。

heap size 超过 `2*live+64` 时从活节点重建，防止频繁 update 产生无界 stale。测试用 fake clock 和慢 timestamp oracle 随机差分，不用 sleep。

## 练习 2：有容量承诺的流式去重草图（生产/开放）

实现 `BoundedIngestionSketch`：根据 expectedInsertions=n、targetFalsePositiveRate=p 计算 Bloom m/k；`observe(canonicalId)` 在未饱和时返回 `admit` 或 `probablyDuplicate`，admit 后插入 Bloom；admitted 达 n 后返回 `saturated`，不继续假装 p 仍成立。ID 限制最大 UTF-16 长度并要求已规范化。

同时对 admitted 流维护大小 sampleSize 的 reservoir sample；随机源注入。stats 返回 m/k/admitted/probablyDuplicate/saturation/sample，不暴露可修改内部数组。不得保存所有 ID。

测试：已 admit ID 再查绝不 admit；空 filter；饱和边界；sampleSize 0/大于 admitted；固定 RNG 步骤；对非恶意随机未插入 ID 估计误报并说明统计容差。

发散：若误拒绝新事件不可接受，Bloom 后必须接什么精确查询？窗口/天级去重怎样 rotate 且避免切换边界 false negative？攻击者可控 ID 时教学 hash 有何风险？
