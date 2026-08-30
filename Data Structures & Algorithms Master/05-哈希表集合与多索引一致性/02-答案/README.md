# 第 05 章参考答案

## 题 1：开放寻址 HashMap

### 1. hash 与槽位

下面使用 FNV-1a 风格的 32-bit 教学 hash，按 UTF-16 code unit 处理字符串。它用于展示机制，不是抗碰撞密码哈希。

```ts
const DELETED: unique symbol = Symbol("deleted");
interface Entry<V> { readonly key: string; value: V }
type Slot<V> = Entry<V> | typeof DELETED | undefined;

function hashString(key: string): number {
  let hash = 0x811c9dc5;
  for (let i = 0; i < key.length; i += 1) {
    hash ^= key.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return hash >>> 0;
}

export class StringHashMap<V> {
  #slots: Array<Slot<V>>;
  #size = 0;
  #used = 0; // OCCUPIED + DELETED

  constructor(initialCapacity = 8) {
    if (!Number.isSafeInteger(initialCapacity) || initialCapacity <= 0) throw new RangeError("bad capacity");
    let capacity = 8;
    while (capacity < initialCapacity) capacity *= 2;
    this.#slots = new Array<Slot<V>>(capacity);
  }
  get size(): number { return this.#size; }

  has(key: string): boolean { return this.#find(key) !== -1; }
  get(key: string): V | undefined {
    const index = this.#find(key);
    return index === -1 ? undefined : (this.#slots[index] as Entry<V>).value;
  }

  set(key: string, value: V): this {
    if (typeof key !== "string") throw new TypeError("key must be a string");
    if ((this.#used + 1) / this.#slots.length > 0.7) {
      const tombstones = this.#used - this.#size;
      this.#rehash(tombstones > this.#size ? this.#slots.length : this.#slots.length * 2);
    }

    const mask = this.#slots.length - 1;
    let index = hashString(key) & mask;
    let firstDeleted = -1;
    for (let probes = 0; probes < this.#slots.length; probes += 1) {
      const slot = this.#slots[index];
      if (slot === undefined) {
        const target = firstDeleted === -1 ? index : firstDeleted;
        this.#slots[target] = { key, value };
        this.#size += 1;
        if (firstDeleted === -1) this.#used += 1;
        return this;
      }
      if (slot === DELETED) {
        if (firstDeleted === -1) firstDeleted = index;
      } else if (slot.key === key) {
        slot.value = value;
        return this;
      }
      index = (index + 1) & mask;
    }
    // 只可能在全表没有 EMPTY 但存在 tombstone 时发生。
    if (firstDeleted !== -1) {
      this.#slots[firstDeleted] = { key, value };
      this.#size += 1;
      return this;
    }
    throw new Error("hash table unexpectedly full");
  }

  delete(key: string): boolean {
    const index = this.#find(key);
    if (index === -1) return false;
    this.#slots[index] = DELETED;
    this.#size -= 1;
    if (this.#size === 0) {
      this.#slots = new Array<Slot<V>>(Math.max(8, this.#slots.length));
      this.#used = 0;
    } else if (this.#used - this.#size > this.#size) {
      this.#rehash(this.#slots.length);
    }
    return true;
  }

  #find(key: string): number {
    const mask = this.#slots.length - 1;
    let index = hashString(key) & mask;
    for (let probes = 0; probes < this.#slots.length; probes += 1) {
      const slot = this.#slots[index];
      if (slot === undefined) return -1;
      if (slot !== DELETED && slot.key === key) return index;
      index = (index + 1) & mask;
    }
    return -1;
  }

  #rehash(capacity: number): void {
    const old = this.#slots;
    this.#slots = new Array<Slot<V>>(capacity);
    this.#size = 0; this.#used = 0;
    for (const slot of old) if (slot !== undefined && slot !== DELETED) this.set(slot.key, slot.value);
  }
}
```

### 2. 正确性与成本

查找只有遇到 EMPTY 才停止；tombstone 不截断探测链，因此删除前已可达的后继键仍可达。插入优先记住首个 tombstone，但继续探测到 EMPTY，以避免同 key 已存在于后面时错误插入重复项。

在哈希均匀、负载受控的假设下，get/set/delete 期望常数探测；最坏碰撞全部聚集时 O(n)。重哈希 O(n)，几何扩容下插入摊还期望 O(1)。空间 O(capacity)。

强制碰撞测试可以把 `hashString` 改为构造函数注入，并在测试传 `() => 0`；生产 API 不必暴露。依次 set a,b,c，delete b，确认 get c 仍成功，再 set d 并确认复用 tombstone、size 正确。随机 oracle 必须包含 stored value 为 undefined，以验证 has 不是 `get() !== undefined`。

## 题 2：TicketIndex

### 1. 事务式步骤

每个步骤包含 `do/undo`；fault injector 在 do 前运行。发生异常时，把已完成步骤逆序撤销。内置 Map/Set 操作若进程 OOM，程序未必有机会恢复；这里主要保证验证/业务异常与可测试提交失败，不夸大为崩溃原子性。

```ts
type TicketStatus = "open" | "pending" | "closed";
interface Ticket { readonly id: string; readonly status: TicketStatus; readonly assignee: string | null; readonly title: string }
interface TicketQuery { readonly status?: TicketStatus; readonly assignee?: string | null }
interface Step { readonly label: string; run(): void; undo(): void }

export class TicketIndex {
  readonly #byId = new Map<string, Ticket>();
  readonly #byStatus = new Map<TicketStatus, Set<string>>();
  readonly #byAssignee = new Map<string | null, Set<string>>();

  constructor(private readonly beforeStep?: (label: string) => void) {}

  get(id: string): Ticket | undefined { return this.#byId.get(id); }

  insert(input: Ticket): void {
    const ticket = this.#normalize(input);
    if (this.#byId.has(ticket.id)) throw new Error(`duplicate ticket: ${ticket.id}`);
    this.#commit([
      this.#addStep(this.#byStatus, ticket.status, ticket.id, "status:add"),
      this.#addStep(this.#byAssignee, ticket.assignee, ticket.id, "assignee:add"),
      { label: "primary:add", run: () => { this.#byId.set(ticket.id, ticket); }, undo: () => { this.#byId.delete(ticket.id); } },
    ]);
  }

  update(input: Ticket): void {
    const next = this.#normalize(input);
    const previous = this.#byId.get(next.id);
    if (previous === undefined) throw new Error(`unknown ticket: ${next.id}`);
    const steps: Step[] = [];
    if (previous.status !== next.status) {
      steps.push(this.#removeStep(this.#byStatus, previous.status, next.id, "status:remove"));
      steps.push(this.#addStep(this.#byStatus, next.status, next.id, "status:add"));
    }
    if (previous.assignee !== next.assignee) {
      steps.push(this.#removeStep(this.#byAssignee, previous.assignee, next.id, "assignee:remove"));
      steps.push(this.#addStep(this.#byAssignee, next.assignee, next.id, "assignee:add"));
    }
    steps.push({ label: "primary:update", run: () => { this.#byId.set(next.id, next); }, undo: () => { this.#byId.set(previous.id, previous); } });
    this.#commit(steps);
  }

  delete(id: string): boolean {
    const previous = this.#byId.get(id);
    if (previous === undefined) return false;
    this.#commit([
      this.#removeStep(this.#byStatus, previous.status, id, "status:remove"),
      this.#removeStep(this.#byAssignee, previous.assignee, id, "assignee:remove"),
      { label: "primary:delete", run: () => { this.#byId.delete(id); }, undo: () => { this.#byId.set(id, previous); } },
    ]);
    return true;
  }

  query(criteria: TicketQuery): readonly Ticket[] {
    const hasStatus = "status" in criteria;
    const hasAssignee = "assignee" in criteria;
    if (!hasStatus && !hasAssignee) throw new Error("at least one indexed criterion is required");
    const statusSet = hasStatus ? this.#byStatus.get(criteria.status!) ?? new Set<string>() : null;
    const assigneeSet = hasAssignee ? this.#byAssignee.get(criteria.assignee!) ?? new Set<string>() : null;
    let ids: Iterable<string>;
    if (statusSet !== null && assigneeSet !== null) {
      const [small, other] = statusSet.size <= assigneeSet.size ? [statusSet, assigneeSet] : [assigneeSet, statusSet];
      ids = [...small].filter((id) => other.has(id));
    } else ids = (statusSet ?? assigneeSet)!;
    return [...ids].sort((a, b) => a.localeCompare(b)).map((id) => this.#byId.get(id)!);
  }

  assertInvariants(): void {
    for (const [id, ticket] of this.#byId) {
      if (!this.#byStatus.get(ticket.status)?.has(id)) throw new Error(`missing status index: ${id}`);
      if (!this.#byAssignee.get(ticket.assignee)?.has(id)) throw new Error(`missing assignee index: ${id}`);
    }
    const check = <K>(index: Map<K, Set<string>>, field: (t: Ticket) => K): void => {
      for (const [key, ids] of index) {
        if (ids.size === 0) throw new Error("empty index bucket");
        for (const id of ids) {
          const ticket = this.#byId.get(id);
          if (ticket === undefined || field(ticket) !== key) throw new Error(`stale secondary id: ${id}`);
        }
      }
    };
    check(this.#byStatus, (t) => t.status);
    check(this.#byAssignee, (t) => t.assignee);
  }

  #normalize(input: Ticket): Ticket {
    if (typeof input.id !== "string" || input.id.trim() === "") throw new Error("empty id");
    if (!(["open", "pending", "closed"] as const).includes(input.status)) throw new Error("bad status");
    if (input.assignee !== null && typeof input.assignee !== "string") throw new Error("bad assignee");
    if (typeof input.title !== "string") throw new Error("bad title");
    return Object.freeze({ ...input });
  }

  #addStep<K>(index: Map<K, Set<string>>, key: K, id: string, label: string): Step {
    let created = false;
    return {
      label,
      run: () => {
        let set = index.get(key);
        if (set?.has(id)) throw new Error(`corrupt index before ${label}: duplicate ${id}`);
        if (!set) { set = new Set(); index.set(key, set); created = true; }
        set.add(id);
      },
      undo: () => { const set = index.get(key)!; set.delete(id); if (created || set.size === 0) index.delete(key); },
    };
  }
  #removeStep<K>(index: Map<K, Set<string>>, key: K, id: string, label: string): Step {
    let removedSet: Set<string> | null = null;
    return {
      label,
      run: () => { const set = index.get(key); if (!set?.has(id)) throw new Error(`corrupt index before ${label}`); set.delete(id); if (set.size === 0) { removedSet = set; index.delete(key); } },
      undo: () => { let set = index.get(key); if (!set) { set = removedSet ?? new Set(); index.set(key, set); } set.add(id); },
    };
  }
  #commit(steps: readonly Step[]): void {
    const done: Step[] = [];
    try {
      for (const step of steps) { this.beforeStep?.(step.label); step.run(); done.push(step); }
    } catch (error) {
      for (let i = done.length - 1; i >= 0; i -= 1) done[i]!.undo();
      throw error;
    }
  }
}
```

### 2. 成本与边界

在常见 Map/Set 实现假设下，单次写期望 O(1)，query 遍历较小桶 O(k)，输出排序 O(r log r)。`assertInvariants()` 是 O(total tickets + index memberships)，只用于测试/后台审计。

fault 测试先保存 `get/query` 的规范化快照，对 insert/update/delete 的每个 label 分别配置 injector 抛错，随后比较快照并调用 assertInvariants。验证错误发生在 commit 前，不应触发任何 step。

这个结构只支持已建索引组合；无条件 query 被明确拒绝，避免偷偷全表扫。大结果需要游标/分页和稳定复合排序键。跨进程、多实例、崩溃恢复与持久化由数据库事务、唯一约束、版本列/锁和索引承担；不要把内存 journal 当成它们的替代。

复写任务：加入 `priority` 二级索引时，不先写代码，先列 insert/update/delete 各增加哪些步骤与不变量；再通过 fault matrix 证明没有漏掉回滚路径。
