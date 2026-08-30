# 第 04 章参考答案

## 题 1：ArrayDeque

### 表示与不变量

`head` 指向逻辑第 0 项，`size` 表示有效项数。逻辑索引 `i` 的物理位置是 `(head+i)%capacity`。空和满由 size 区分。结构修改递增 version，迭代器保存创建时版本。

```ts
export class ArrayDeque<T> implements Iterable<T> {
  #buffer: Array<T | undefined>;
  #head = 0;
  #size = 0;
  #version = 0;

  constructor(initialCapacity = 8) {
    if (!Number.isSafeInteger(initialCapacity) || initialCapacity <= 0) {
      throw new RangeError("initialCapacity must be a positive safe integer");
    }
    this.#buffer = new Array<T | undefined>(initialCapacity);
  }

  get size(): number { return this.#size; }

  #physical(logicalIndex: number): number {
    return (this.#head + logicalIndex) % this.#buffer.length;
  }

  #grow(): void {
    const nextCapacity = this.#buffer.length * 2;
    if (!Number.isSafeInteger(nextCapacity)) throw new RangeError("deque capacity overflow");
    const next = new Array<T | undefined>(nextCapacity);
    for (let i = 0; i < this.#size; i += 1) next[i] = this.#buffer[this.#physical(i)];
    this.#buffer = next;
    this.#head = 0;
  }

  pushFront(value: T): void {
    if (this.#size === this.#buffer.length) this.#grow();
    this.#head = (this.#head - 1 + this.#buffer.length) % this.#buffer.length;
    this.#buffer[this.#head] = value;
    this.#size += 1; this.#version += 1;
  }

  pushBack(value: T): void {
    if (this.#size === this.#buffer.length) this.#grow();
    this.#buffer[this.#physical(this.#size)] = value;
    this.#size += 1; this.#version += 1;
  }

  popFront(): T | undefined {
    if (this.#size === 0) return undefined;
    const value = this.#buffer[this.#head];
    this.#buffer[this.#head] = undefined;
    this.#head = (this.#head + 1) % this.#buffer.length;
    this.#size -= 1; this.#version += 1;
    if (this.#size === 0) this.#head = 0;
    return value;
  }

  popBack(): T | undefined {
    if (this.#size === 0) return undefined;
    const index = this.#physical(this.#size - 1);
    const value = this.#buffer[index];
    this.#buffer[index] = undefined;
    this.#size -= 1; this.#version += 1;
    if (this.#size === 0) this.#head = 0;
    return value;
  }

  peekFront(): T | undefined {
    return this.#size === 0 ? undefined : this.#buffer[this.#head];
  }

  peekBack(): T | undefined {
    return this.#size === 0 ? undefined : this.#buffer[this.#physical(this.#size - 1)];
  }

  [Symbol.iterator](): Iterator<T> {
    const expectedVersion = this.#version;
    let logicalIndex = 0;
    return {
      next: (): IteratorResult<T> => {
        if (this.#version !== expectedVersion) throw new Error("deque modified during iteration");
        if (logicalIndex >= this.#size) return { done: true, value: undefined };
        const value = this.#buffer[this.#physical(logicalIndex)] as T;
        logicalIndex += 1;
        return { done: false, value };
      },
    };
  }
}
```

`as T` 只出现在内部已由 `logicalIndex < size` 证明属于有效区的位置；即使 T 本身是 undefined，这个位置仍是一个合法元素。公共 pop 的 union 仍有语义歧义，这是 API 契约限制，不是内部正确性问题。

扩容前逻辑序列是 `old[(head+i)%oldCapacity]`；逐项复制到 `next[i]` 后顺序不变，head 可安全变为 0。几何增长下，一个元素在容量翻倍时才被搬移，总搬移次数形成几何级数，小于最终容量常数倍，因此 push 摊还 O(1)。

随机测试维护 `model: T[]`，pushFront 对应 `unshift`、popFront 对应 `shift`（oracle 小且不用于被测性能）；每一步比较 `[...deque]`、size、两端值。随机测试应固定 seed，并在失败时输出最短操作前缀。

## 题 2：TelemetryBuffer

### 设计选择

用两个 FIFO deque 分别保存 critical 和 best-effort。全局 drain 时比较两个队首 sequence，取较小者，因此不需要第三份全量索引。critical 需要空间时能 O(1) 淘汰最旧 best-effort。只允许一个 lease，使 rollback 语义清晰。

下面假定复用题 1 的 ArrayDeque。

```ts
type Priority = "critical" | "bestEffort";
interface TelemetryEvent {
  readonly sequence: number;
  readonly byteSize: number;
  readonly priority: Priority;
  readonly payload: unknown;
}
interface BufferStats {
  readonly bufferedBytes: number; readonly reservedBytes: number;
  readonly bufferedCount: number; readonly droppedCritical: number;
  readonly droppedBestEffort: number; readonly lastDroppedSequence: number | null;
}
interface DrainLease {
  readonly events: readonly TelemetryEvent[];
  commit(): void;
  rollback(): void;
}

export class TelemetryBuffer {
  readonly #critical = new ArrayDeque<TelemetryEvent>();
  readonly #bestEffort = new ArrayDeque<TelemetryEvent>();
  #bufferedBytes = 0;
  #reservedBytes = 0;
  #lastSequence = -1;
  #activeLease = false;
  #droppedCritical = 0;
  #droppedBestEffort = 0;
  #lastDroppedSequence: number | null = null;

  constructor(readonly maxBytes: number) {
    if (!Number.isSafeInteger(maxBytes) || maxBytes <= 0) throw new RangeError("bad maxBytes");
  }

  append(event: TelemetryEvent): boolean {
    this.#validateNewEvent(event);
    // 即使事件最终被丢弃，sequence 也已经被消费，防止之后倒序重用。
    this.#lastSequence = event.sequence;
    if (event.byteSize > this.maxBytes) { this.#recordDrop(event); return false; }

    if (event.priority === "bestEffort") {
      if (!this.#fits(event.byteSize)) { this.#recordDrop(event); return false; }
      this.#bestEffort.pushBack(event);
    } else {
      while (!this.#fits(event.byteSize) && this.#bestEffort.size > 0) this.#dropOldest(this.#bestEffort);
      while (!this.#fits(event.byteSize) && this.#critical.size > 0) this.#dropOldest(this.#critical);
      // reserved 批次不可被淘汰，所以清空可见队列后仍可能放不下。
      if (!this.#fits(event.byteSize)) { this.#recordDrop(event); return false; }
      this.#critical.pushBack(event);
    }
    this.#bufferedBytes += event.byteSize;
    return true;
  }

  beginDrain(maxBatchBytes: number): DrainLease | null {
    if (this.#activeLease) throw new Error("a drain lease is already active");
    if (!Number.isSafeInteger(maxBatchBytes) || maxBatchBytes <= 0) throw new RangeError("bad batch size");
    const events: TelemetryEvent[] = [];
    let bytes = 0;
    while (true) {
      const c = this.#critical.peekFront();
      const b = this.#bestEffort.peekFront();
      const next = c === undefined ? b : b === undefined ? c : c.sequence < b.sequence ? c : b;
      if (next === undefined || bytes + next.byteSize > maxBatchBytes) break;
      const removed = next.priority === "critical" ? this.#critical.popFront() : this.#bestEffort.popFront();
      events.push(removed!); bytes += next.byteSize;
    }
    if (events.length === 0) return null;

    this.#bufferedBytes -= bytes;
    this.#reservedBytes += bytes;
    this.#activeLease = true;
    let finalized = false;
    const finish = (rollback: boolean): void => {
      if (finalized) throw new Error("lease already finalized");
      finalized = true;
      if (rollback) {
        for (let i = events.length - 1; i >= 0; i -= 1) {
          const event = events[i]!;
          (event.priority === "critical" ? this.#critical : this.#bestEffort).pushFront(event);
        }
        this.#bufferedBytes += bytes;
      }
      this.#reservedBytes -= bytes;
      this.#activeLease = false;
    };
    return { events: Object.freeze([...events]), commit: () => finish(false), rollback: () => finish(true) };
  }

  get stats(): BufferStats {
    return {
      bufferedBytes: this.#bufferedBytes, reservedBytes: this.#reservedBytes,
      bufferedCount: this.#critical.size + this.#bestEffort.size,
      droppedCritical: this.#droppedCritical, droppedBestEffort: this.#droppedBestEffort,
      lastDroppedSequence: this.#lastDroppedSequence,
    };
  }

  #fits(bytes: number): boolean {
    return this.#bufferedBytes + this.#reservedBytes + bytes <= this.maxBytes;
  }
  #dropOldest(queue: ArrayDeque<TelemetryEvent>): void {
    const event = queue.popFront()!;
    this.#bufferedBytes -= event.byteSize;
    this.#recordDrop(event);
  }
  #recordDrop(event: TelemetryEvent): void {
    if (event.priority === "critical") this.#droppedCritical += 1;
    else this.#droppedBestEffort += 1;
    this.#lastDroppedSequence = event.sequence;
  }
  #validateNewEvent(event: TelemetryEvent): void {
    if (!Number.isSafeInteger(event.sequence) || event.sequence <= this.#lastSequence) throw new Error("sequence must increase");
    if (!Number.isSafeInteger(event.byteSize) || event.byteSize <= 0) throw new Error("byteSize must be positive");
    if (event.priority !== "critical" && event.priority !== "bestEffort") throw new Error("bad priority");
  }
}
```

### 不变量与失败边界

append 只在 fits 后增加 buffered；evict 同步减字节；beginDrain 把同一数值从 buffered 移到 reserved；commit 只减 reserved；rollback 从 reserved 移回 buffered。因此容量总和不会因状态转换变化或超过上限。

rollback 按批次逆序 pushFront 到各自优先级队列，恢复每条子队列内的 sequence 顺序；新事件只在尾部，之后 merge 两个队首仍得到全局顺序。指标只保存常数个计数与最后序号，不会因长期丢弃自身造成内存泄漏。

局限也必须明说：页面刷新、进程崩溃会丢内存数据；两个 tab 各有独立容量与 sequence；payload 在 append 后若可变，调用方还能改内容而 byteSize 不变，生产版应复制/序列化或要求不可变；单 lease 阻止并行 flush。绝不能丢的审计数据需要先持久化到可靠本地/服务端存储、确认后再删除，并设计幂等 ID，本题缓冲不能提供该保证。

复写任务：只看状态转换表重写 lease，然后加入 `close()`：活动 lease 如何处理、之后 append 返回什么、如何避免调用方忘记 finalize 永久占用 reserved？给出你选择的契约与测试。

