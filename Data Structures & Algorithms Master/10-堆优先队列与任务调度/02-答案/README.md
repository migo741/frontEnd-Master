# 第 10 章参考答案

## 题 1：BinaryHeap

```ts
export class BinaryHeap<T> {
  #data: T[];
  constructor(
    private readonly compare: (a: T, b: T) => number,
    values: readonly T[] = [],
  ) {
    this.#data = [...values];
    for (let i = Math.floor(this.#data.length / 2) - 1; i >= 0; i -= 1) this.#siftDown(i);
  }
  get size(): number { return this.#data.length; }
  peek(): T | undefined { return this.#data[0]; }

  push(value: T): void {
    this.#data.push(value);
    let index = this.#data.length - 1;
    while (index > 0) {
      const parent = Math.floor((index - 1) / 2);
      const parentValue = this.#data[parent]!;
      if (this.compare(parentValue, value) <= 0) break;
      this.#data[index] = parentValue;
      index = parent;
    }
    this.#data[index] = value;
  }

  pop(): T | undefined {
    const oldLength = this.#data.length;
    if (oldLength === 0) return undefined;
    const root = this.#data[0] as T;
    if (oldLength === 1) {
      this.#data.pop();
      return root;
    }
    const last = this.#data.pop() as T;
    this.#data[0] = last;
    this.#siftDown(0);
    return root;
  }

  #siftDown(start: number): void {
    const value = this.#data[start]!;
    let index = start;
    while (true) {
      const left = index * 2 + 1;
      if (left >= this.#data.length) break;
      const right = left + 1;
      let child = left;
      if (right < this.#data.length && this.compare(this.#data[right]!, this.#data[left]!) < 0) child = right;
      if (this.compare(value, this.#data[child]!) <= 0) break;
      this.#data[index] = this.#data[child]!;
      index = child;
    }
    this.#data[index] = value;
  }
}
```

实现先读取旧 `length` 判断空，因此即使 T 合法为 `undefined`，内部也不会把一个真实元素误判为空。不过公共返回类型仍无法让调用方区分“空堆”和“弹出的值就是 undefined”；关键 API 可改为 Result union。

push 的不变量是除 index-parent 边外全堆合法；siftDown 类似。每轮 index 严格向根/叶移动，最多树高 O(log n)。heapify 自最后非叶向上时，两个子堆已合法，siftDown 后当前子树合法；归纳到根得到全堆。

## 题 2：ExpirationQueue

### 1. 句柄与 entry 分离

句柄保存当前真相，heap entry 是某个 generation 的快照。reschedule 更新句柄并推新快照；旧 entry 不修改，稍后判 stale。

```ts
export interface ExpirationHandle<T> { readonly value: T }
const HANDLE: unique symbol = Symbol("expiration-handle");
interface HandleState<T> {
  readonly owner: object; readonly value: T; active: boolean;
  deadline: number; generation: number; sequence: number;
}
class InternalHandle<T> implements ExpirationHandle<T> {
  readonly [HANDLE]: HandleState<T>;
  constructor(public readonly value: T, state: HandleState<T>) {
    this[HANDLE] = state;
  }
}
interface Entry<T> {
  readonly handle: HandleState<T>; readonly deadline: number;
  readonly generation: number; readonly sequence: number;
}
type TimerToken = unknown;

interface ExpirationOptions<T> {
  readonly now: () => number;
  readonly setTimer: (callback: () => void, delayMs: number) => TimerToken;
  readonly clearTimer: (token: TimerToken) => void;
  readonly maxDelay: number;
  readonly maxBatch: number;
  readonly onExpire: (value: T) => void;
  readonly onError: (error: unknown) => void;
}

export class ExpirationQueue<T> {
  readonly #owner = Object.freeze({});
  #heap = new BinaryHeap<Entry<T>>(
    (a, b) => a.deadline - b.deadline || a.sequence - b.sequence,
  );
  readonly #active = new Set<HandleState<T>>();
  #timer: TimerToken | null = null;
  #sequence = 0;
  #firing = false;

  constructor(private readonly options: ExpirationOptions<T>) {
    if (!Number.isFinite(options.maxDelay) || options.maxDelay <= 0) throw new RangeError("bad maxDelay");
    if (!Number.isSafeInteger(options.maxBatch) || options.maxBatch <= 0) throw new RangeError("bad maxBatch");
  }

  schedule(value: T, deadline: number): ExpirationHandle<T> {
    this.#validateDeadline(deadline);
    const state: HandleState<T> = {
      owner: this.#owner, value, active: true, deadline,
      generation: 0, sequence: this.#nextSequence(),
    };
    this.#active.add(state);
    this.#pushCurrent(state);
    if (!this.#firing) this.#arm();
    return new InternalHandle(value, state);
  }

  cancel(handle: ExpirationHandle<T>): boolean {
    const state = this.#state(handle);
    if (state === null || !state.active) return false;
    state.active = false; state.generation += 1;
    this.#active.delete(state);
    this.#maybeRebuild();
    if (!this.#firing) this.#arm();
    return true;
  }

  reschedule(handle: ExpirationHandle<T>, deadline: number): boolean {
    this.#validateDeadline(deadline);
    const state = this.#state(handle);
    if (state === null || !state.active) return false;
    const nextSequence = this.#nextSequence();
    state.deadline = deadline;
    state.generation += 1;
    state.sequence = nextSequence;
    this.#pushCurrent(state);
    this.#maybeRebuild();
    if (!this.#firing) this.#arm();
    return true;
  }

  #fire(): void {
    this.#timer = null;
    this.#firing = true;
    try {
      let processed = 0;
      while (processed < this.options.maxBatch) {
        this.#discardStaleTop();
        const entry = this.#heap.peek();
        if (entry === undefined || entry.deadline > this.options.now()) break;
        this.#heap.pop();
        const state = entry.handle;
        if (!this.#isCurrent(entry)) continue;
        state.active = false;
        this.#active.delete(state);
        processed += 1;
        try { this.options.onExpire(state.value); }
        catch (error) { this.options.onError(error); }
      }
    } finally {
      this.#firing = false;
      this.#maybeRebuild();
      this.#arm();
    }
  }

  #arm(): void {
    if (this.#timer !== null) { this.options.clearTimer(this.#timer); this.#timer = null; }
    this.#discardStaleTop();
    const next = this.#heap.peek();
    if (next === undefined) return;
    const delay = Math.min(this.options.maxDelay, Math.max(0, next.deadline - this.options.now()));
    this.#timer = this.options.setTimer(() => this.#fire(), delay);
  }

  #discardStaleTop(): void {
    while (this.#heap.peek() !== undefined && !this.#isCurrent(this.#heap.peek()!)) this.#heap.pop();
  }
  #isCurrent(entry: Entry<T>): boolean {
    const s = entry.handle;
    return s.active && s.owner === this.#owner && s.generation === entry.generation
      && s.deadline === entry.deadline && s.sequence === entry.sequence;
  }
  #pushCurrent(state: HandleState<T>): void {
    this.#heap.push({ handle: state, deadline: state.deadline, generation: state.generation, sequence: state.sequence });
  }
  #maybeRebuild(): void {
    if (this.#heap.size <= this.#active.size * 2 + 64) return;
    this.#heap = new BinaryHeap(
      (a: Entry<T>, b: Entry<T>) => a.deadline - b.deadline || a.sequence - b.sequence,
      [...this.#active].map((state) => ({ handle: state, deadline: state.deadline, generation: state.generation, sequence: state.sequence })),
    );
  }
  #state(handle: ExpirationHandle<T>): HandleState<T> | null {
    if (!(handle instanceof InternalHandle)) return null;
    const state = (handle as InternalHandle<T>)[HANDLE];
    return state.owner === this.#owner ? state : null;
  }
  #nextSequence(): number {
    if (this.#sequence >= Number.MAX_SAFE_INTEGER) throw new RangeError("sequence exhausted");
    this.#sequence += 1; return this.#sequence;
  }
  #validateDeadline(value: number): void {
    if (!Number.isFinite(value)) throw new RangeError("deadline must be finite");
  }
}
```

### 2. 必须审查的两个细节

第一，上面的 BinaryHeap `pop` 对 undefined 元素有歧义，但 Entry 永远是对象，因此在本类中安全；通用堆本身仍应按题 1 注释修正。

第二，假 scheduler 的 `setTimer` 必须像真实 timer 一样延后调用，不能在函数内部同步执行回调，否则 `this.#timer = setTimer(...)` 会产生重入赋值竞态。把这一点写进注入接口契约。

### 3. 正确性、复杂度与生产边界

比较器按 deadline/sequence 全序，最早当前 entry 必在堆顶（清 stale 后）。只有 current generation 能触发；触发先 active=false，因此 callback 重入 cancel 返回 false，同一 handle 至多触发一次。arm 总先清旧 token 再建新 token，因此至多一个底层 timer。maxDelay 只会提前分段唤醒，不会把未来任务提前执行，因为 fire 再比较 deadline<=now。

schedule/reschedule O(log h)，cancel 本身 O(1) 加可能 O(a) rebuild；按阈值触发后可作摊还分析。fire 每项 pop O(log h)。空间受 active 与重建阈值约束为 O(active)，而不是随历史 reschedule 永久增长。

Fake scheduler 保存 `{due,callback,token}`，`advanceTo(t)` 按 due/token 顺序执行所有到期回调；同时统计未取消 token。测试 callback 内 schedule 一个立即到期项，确保 finally 重新 arm；一次 100 项到期、maxBatch=10，应观察多次 0-delay 回调且每批不超过 10。

本实现没有持久化。进程崩溃后所有任务消失；多实例各自可能执行同一业务项；timer 延迟也不是实时保证。生产延时任务需要数据库/消息队列保存状态、租约/可见性超时、幂等消费、重试与死信。内存堆只负责单进程“下一个是谁”的算法核心。

复写任务：先不看代码，画 handle generation 0、reschedule 到 1、旧 entry 到堆顶的状态表。再实现 `nextDeadline(): number|null`，确保它清理 stale 但不触发任务，也不泄露可修改 entry。
