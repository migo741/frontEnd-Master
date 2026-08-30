# 第 19 章参考答案

## 题 1：LruTtlCache

### 1. 三份状态与一个事实源

Map/双链中的 live node 是事实源；expiry heap entry 只是某 generation 的调度快照，可以 stale。删除节点先从 Map/双链同步摘除，再安全通知 observer。

```ts
type EvictionReason = "capacity" | "expired" | "deleted";
interface CacheNode<K, V> {
  readonly key: K; value: V; expiresAt: number; generation: number;
  prev: CacheNode<K, V> | null; next: CacheNode<K, V> | null; linked: boolean;
}
interface Expiry<K, V> {
  readonly node: CacheNode<K, V>; readonly expiresAt: number;
  readonly generation: number; readonly sequence: number;
}

export class LruTtlCache<K, V> {
  readonly #map = new Map<K, CacheNode<K, V>>();
  #head: CacheNode<K, V> | null = null;
  #tail: CacheNode<K, V> | null = null;
  #heap = new BinaryHeap<Expiry<K, V>>((a, b) =>
    a.expiresAt - b.expiresAt || a.sequence - b.sequence,
  );
  #sequence = 0;

  constructor(private readonly options: {
    readonly maxEntries: number; readonly now: () => number;
    readonly onEvict?: (key: K, value: V, reason: EvictionReason) => void;
  }) {
    if (!Number.isSafeInteger(options.maxEntries) || options.maxEntries < 0) throw new RangeError("bad maxEntries");
  }

  get size(): number { this.#purge(); return this.#map.size; }

  get(key: K): V | undefined {
    this.#purge();
    const node = this.#map.get(key);
    if (!node) return undefined;
    this.#moveToHead(node);
    return node.value;
  }
  has(key: K): boolean {
    this.#purge();
    const node = this.#map.get(key);
    if (!node) return false;
    this.#moveToHead(node);
    return true;
  }

  set(key: K, value: V, ttlMs: number): boolean {
    if (!Number.isFinite(ttlMs) || ttlMs <= 0) { this.delete(key); return false; }
    const now = this.options.now();
    if (!Number.isFinite(now) || !Number.isFinite(now + ttlMs)) throw new RangeError("bad clock/TTL");
    this.#purgeAt(now);
    if (this.options.maxEntries === 0) return false;
    const expiresAt = now + ttlMs;
    let node = this.#map.get(key);
    if (node) {
      node.value = value; node.expiresAt = expiresAt; node.generation += 1;
      this.#moveToHead(node);
    } else {
      node = { key, value, expiresAt, generation: 0, prev: null, next: null, linked: true };
      this.#map.set(key, node); this.#linkHead(node);
    }
    this.#heap.push({ node, expiresAt, generation: node.generation, sequence: this.#nextSequence() });
    while (this.#map.size > this.options.maxEntries) this.#remove(this.#tail!, "capacity");
    this.#maybeRebuild();
    return true;
  }

  delete(key: K): boolean {
    this.#purge();
    const node = this.#map.get(key);
    if (!node) return false;
    this.#remove(node, "deleted"); this.#maybeRebuild(); return true;
  }

  #purge(): void { this.#purgeAt(this.options.now()); }
  #purgeAt(now: number): void {
    if (!Number.isFinite(now)) throw new RangeError("clock must be finite");
    while (this.#heap.peek() !== undefined && this.#heap.peek()!.expiresAt <= now) {
      const entry = this.#heap.pop()!;
      const node = entry.node;
      if (node.linked && node.generation === entry.generation && node.expiresAt === entry.expiresAt) {
        this.#remove(node, "expired");
      }
    }
    this.#maybeRebuild();
  }

  #moveToHead(node: CacheNode<K, V>): void {
    if (node === this.#head) return;
    this.#unlink(node); this.#linkHead(node);
  }
  #unlink(node: CacheNode<K, V>): void {
    if (node.prev) node.prev.next = node.next; else this.#head = node.next;
    if (node.next) node.next.prev = node.prev; else this.#tail = node.prev;
    node.prev = null; node.next = null;
  }
  #linkHead(node: CacheNode<K, V>): void {
    node.prev = null; node.next = this.#head;
    if (this.#head) this.#head.prev = node; else this.#tail = node;
    this.#head = node;
  }
  #remove(node: CacheNode<K, V>, reason: EvictionReason): void {
    this.#unlink(node); this.#map.delete(node.key); node.linked = false; node.generation += 1;
    try { this.options.onEvict?.(node.key, node.value, reason); } catch { /* observer 不得破坏缓存 */ }
  }
  #maybeRebuild(): void {
    if (this.#heap.size <= this.#map.size * 2 + 64) return;
    this.#heap = new BinaryHeap(
      (a: Expiry<K, V>, b: Expiry<K, V>) => a.expiresAt - b.expiresAt || a.sequence - b.sequence,
      [...this.#map.values()].map((node) => ({
        node, expiresAt: node.expiresAt, generation: node.generation, sequence: this.#nextSequence(),
      })),
    );
  }
  #nextSequence(): number {
    if (this.#sequence >= Number.MAX_SAFE_INTEGER) throw new RangeError("sequence exhausted");
    this.#sequence += 1; return this.#sequence;
  }
}
```

### 2. 正确性与成本

Map/双链操作与第03章相同；move 不改变 Map size。每个当前 node 有一个最新 expiresAt/generation；heap 可有旧版本，但 purge 只有 exact match 才删除 live node。更新、删除会使旧 entry stale。rebuild 将 heap 恢复为每 live node 一项，历史更新不能导致无界增长。

get/has 的链表部分期望 O(1)，但 purge 可能弹出 e 个到期项，O(e log h)；set 推 heap O(log h)，容量淘汰 O(numberEvicted)。这些成本可对一串操作摊还，因为每 entry 至多 pop 一次。空间因重建阈值 O(live)。

`get` 返回 undefined 仍无法区分 miss 与缓存值 undefined；调用方可先 has，但本题 has 会刷新 recency，两次操作也有时钟变化。更好的关键 API可返回 `{hit:true,value}|{hit:false}`。

该缓存没有 singleflight、多租户 key、权重、持久化或跨实例失效。权限/计费等安全敏感结果不能只依赖过期缓存。onEvict 吞错应接入独立错误报告，而不是静默。

## 题 2：Bloom + Reservoir

```ts
type Observation = "admit" | "probablyDuplicate" | "saturated";
interface SketchStats {
  readonly bitCount: number; readonly hashCount: number; readonly admitted: number;
  readonly probablyDuplicate: number; readonly saturated: boolean;
  readonly sample: readonly string[];
}

function fnv1a(text: string, seed: number): number {
  let h = (0x811c9dc5 ^ seed) >>> 0;
  for (let i = 0; i < text.length; i += 1) {
    h ^= text.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h;
}

export class BoundedIngestionSketch {
  readonly #bits: Uint8Array;
  readonly #m: number;
  readonly #k: number;
  readonly #sample: string[] = [];
  #admitted = 0;
  #probablyDuplicate = 0;

  constructor(private readonly options: {
    readonly expectedInsertions: number;
    readonly targetFalsePositiveRate: number;
    readonly sampleSize: number;
    readonly random: () => number;
    readonly maxIdCodeUnits?: number;
  }) {
    const { expectedInsertions: n, targetFalsePositiveRate: p, sampleSize } = options;
    if (!Number.isSafeInteger(n) || n <= 0 || !(p > 0 && p < 1)) throw new RangeError("bad n/p");
    if (!Number.isSafeInteger(sampleSize) || sampleSize < 0) throw new RangeError("bad sampleSize");
    this.#m = Math.max(8, Math.ceil((-n * Math.log(p)) / (Math.log(2) ** 2)));
    this.#k = Math.max(1, Math.round((this.#m / n) * Math.log(2)));
    if (!Number.isSafeInteger(this.#m) || this.#m > 800_000_000) throw new RangeError("bit budget too large");
    this.#bits = new Uint8Array(Math.ceil(this.#m / 8));
  }

  observe(id: string): Observation {
    this.#validateId(id);
    if (this.#admitted >= this.options.expectedInsertions) return "saturated";
    const positions = this.#positions(id);
    if (positions.every((p) => this.#getBit(p))) {
      this.#probablyDuplicate += 1; return "probablyDuplicate";
    }
    const seen = this.#admitted + 1;
    // 随机源是可注入外部依赖，必须在修改 Bloom 位图前读取并验证。
    const replacementSlot = this.#replacementSlot(seen);
    for (const p of positions) this.#setBit(p);
    this.#admitted = seen;
    if (replacementSlot !== null) {
      if (replacementSlot === this.#sample.length) this.#sample.push(id);
      else this.#sample[replacementSlot] = id;
    }
    return "admit";
  }

  get stats(): SketchStats {
    return {
      bitCount: this.#m, hashCount: this.#k, admitted: this.#admitted,
      probablyDuplicate: this.#probablyDuplicate,
      saturated: this.#admitted >= this.options.expectedInsertions,
      sample: Object.freeze([...this.#sample]),
    };
  }

  #positions(id: string): number[] {
    const h1 = fnv1a(id, 0x9e3779b9);
    let h2 = fnv1a(id, 0x85ebca6b) | 1; // 非零奇数步长
    h2 >>>= 0;
    const out = new Array<number>(this.#k);
    for (let i = 0; i < this.#k; i += 1) {
      out[i] = (((h1 + Math.imul(i, h2)) >>> 0) % this.#m);
    }
    return out;
  }
  #getBit(position: number): boolean {
    const byte = Math.floor(position / 8), mask = 1 << (position % 8);
    return (this.#bits[byte]! & mask) !== 0;
  }
  #setBit(position: number): void {
    const byte = Math.floor(position / 8), mask = 1 << (position % 8);
    this.#bits[byte] = this.#bits[byte]! | mask;
  }
  #replacementSlot(seen: number): number | null {
    const k = this.options.sampleSize;
    if (k === 0) return null;
    if (this.#sample.length < k) return this.#sample.length;
    const r = this.options.random();
    if (!(r >= 0 && r < 1)) throw new Error("random must return [0,1)");
    const j = Math.floor(r * seen);
    return j < k ? j : null;
  }
  #validateId(id: string): void {
    const max = this.options.maxIdCodeUnits ?? 1024;
    if (typeof id !== "string" || id.length === 0 || id.length > max || id !== id.normalize("NFC")) {
      throw new Error("id must be non-empty, bounded, NFC canonical text");
    }
  }
}
```

### 运算符与事务顺序

位置计算把 32-bit 无符号转换和取模分别加括号，避免位运算与 `%` 的优先级改变公式。随机源也在任何 bit/admitted mutation 前读取并验证；若它抛错或返回非法值，调用前后状态不变。这两点分别防止“公式正确、语言表达错位”和“外部依赖失败留下半更新”。

### 语义与边界

一个 admitted ID 的 k 位都被置 1，且饱和前不清位，所以再次 observe 不会返回 admit。未插入 ID 可能碰巧全 1，因此 probablyDuplicate 不能用于不可误拒业务；应去精确数据库/Set 确认。达到 n 后统一 saturated，让调用方 rotate/rebuild，而不是让误报率无声恶化。

位置计算 O(k)，bit 空间 O(m)，reservoir O(sampleSize)。双哈希只是近似生成 k 个位置，理论独立假设与攻击安全都不严格；外部恶意 ID 应使用成熟、可能密钥化的实现。

测试统计误报时必须使用从未插入且与训练数据独立的 ID，报告样本量和置信波动。sample 对 admitted 流均匀，而 Bloom false positive 已让它不代表所有真实唯一事件。

复写任务：用固定 seed 对 1000 次 observe 做状态快照；故障注入 RNG 非法时，证明调用前后位图、计数和样本完全相同。然后故意去掉位置公式括号，用一个具体 h1/h2/m 比较结果。
