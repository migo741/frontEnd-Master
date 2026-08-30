# 第 09 章参考答案

## 题 1：AVL OrderedSet

```ts
interface AvlNode<T> { key: T; height: number; left: AvlNode<T> | null; right: AvlNode<T> | null }
type Comparator<T> = (a: T, b: T) => number;
const height = <T>(node: AvlNode<T> | null): number => node?.height ?? 0;

export class AvlOrderedSet<T> implements Iterable<T> {
  #root: AvlNode<T> | null = null;
  #size = 0;
  constructor(private readonly compare: Comparator<T>) {}
  get size(): number { return this.#size; }

  has(value: T): boolean {
    let node = this.#root;
    while (node !== null) {
      const c = this.compare(value, node.key);
      if (c === 0) return true;
      node = c < 0 ? node.left : node.right;
    }
    return false;
  }

  add(value: T): boolean {
    const result = this.#insert(this.#root, value);
    this.#root = result.node;
    if (result.inserted) this.#size += 1;
    return result.inserted;
  }

  #insert(node: AvlNode<T> | null, key: T): { node: AvlNode<T>; inserted: boolean } {
    if (node === null) return { node: { key, height: 1, left: null, right: null }, inserted: true };
    const relation = this.compare(key, node.key);
    if (relation === 0) return { node, inserted: false };
    let inserted: boolean;
    if (relation < 0) {
      const result = this.#insert(node.left, key); node.left = result.node; inserted = result.inserted;
    } else {
      const result = this.#insert(node.right, key); node.right = result.node; inserted = result.inserted;
    }
    if (!inserted) return { node, inserted: false };
    this.#update(node);
    return { node: this.#rebalance(node), inserted: true };
  }

  #update(node: AvlNode<T>): void {
    node.height = 1 + Math.max(height(node.left), height(node.right));
  }
  #rotateLeft(x: AvlNode<T>): AvlNode<T> {
    const y = x.right!; const middle = y.left;
    y.left = x; x.right = middle;
    this.#update(x); this.#update(y);
    return y;
  }
  #rotateRight(y: AvlNode<T>): AvlNode<T> {
    const x = y.left!; const middle = x.right;
    x.right = y; y.left = middle;
    this.#update(y); this.#update(x);
    return x;
  }
  #rebalance(node: AvlNode<T>): AvlNode<T> {
    const balance = height(node.left) - height(node.right);
    if (balance > 1) {
      if (height(node.left!.left) < height(node.left!.right)) node.left = this.#rotateLeft(node.left!);
      return this.#rotateRight(node);
    }
    if (balance < -1) {
      if (height(node.right!.right) < height(node.right!.left)) node.right = this.#rotateRight(node.right!);
      return this.#rotateLeft(node);
    }
    return node;
  }

  *[Symbol.iterator](): Iterator<T> {
    const stack: AvlNode<T>[] = [];
    let current = this.#root;
    while (current !== null || stack.length > 0) {
      while (current !== null) { stack.push(current); current = current.left; }
      current = stack.pop()!;
      yield current.key;
      current = current.right;
    }
  }
}
```

递归 insert 的深度由 AVL 不变量限制为 O(log n)，因此不同于外部任意深树。沿路径每层做常数工作和最多两个旋转，时间 O(log n)，空间 O(log n) 调用栈；遍历 O(n)。

测试 validator 可递归返回 `{height,count,min,max}`，每节点检查左右边界、`cachedHeight===1+max` 和 `abs(balance)<=1`。validator 是测试 oracle，不复用 `#update/#rebalance`。对 10,000 节点可用宽松上界 `height <= 2 * ceil(log2(n+1))` 捕获退化，而不必背 AVL 精确常数。

## 题 2：OrganizationTreeIndex

### 内部模型与构建

```ts
interface OrgRow { readonly id: string; readonly parentId: string | null }
interface OrgNode { readonly id: string; parentId: string | null; readonly children: Set<string>; subtreeSize: number }

export class OrganizationTreeIndex {
  readonly #nodes = new Map<string, OrgNode>();
  readonly #rootId: string;

  constructor(rows: readonly OrgRow[]) {
    for (const row of rows) {
      if (typeof row.id !== "string" || row.id.trim() === "") throw new Error("empty id");
      if (this.#nodes.has(row.id)) throw new Error(`duplicate id: ${row.id}`);
      this.#nodes.set(row.id, { id: row.id, parentId: row.parentId, children: new Set(), subtreeSize: 1 });
    }
    const roots: string[] = [];
    for (const node of this.#nodes.values()) {
      if (node.parentId === null) { roots.push(node.id); continue; }
      if (node.parentId === node.id) throw new Error(`self parent: ${node.id}`);
      const parent = this.#nodes.get(node.parentId);
      if (parent === undefined) throw new Error(`orphan ${node.id}: ${node.parentId}`);
      parent.children.add(node.id);
    }
    if (roots.length !== 1) throw new Error(`expected exactly one root, got ${roots.length}`);
    this.#rootId = roots[0]!;

    const visited = new Set<string>();
    const stack: Array<{ id: string; exiting: boolean }> = [{ id: this.#rootId, exiting: false }];
    while (stack.length > 0) {
      const frame = stack.pop()!;
      const node = this.#nodes.get(frame.id)!;
      if (frame.exiting) {
        let size = 1;
        for (const child of node.children) size += this.#nodes.get(child)!.subtreeSize;
        node.subtreeSize = size;
        continue;
      }
      if (visited.has(frame.id)) throw new Error(`cycle or repeated parent at ${frame.id}`);
      visited.add(frame.id);
      stack.push({ id: frame.id, exiting: true });
      for (const child of [...node.children].reverse()) stack.push({ id: child, exiting: false });
    }
    if (visited.size !== this.#nodes.size) throw new Error("disconnected cycle detected");
  }

  get rootId(): string { return this.#rootId; }

  ancestors(id: string): readonly string[] {
    const result: string[] = [];
    let current = this.#require(id).parentId;
    while (current !== null) { result.push(current); current = this.#nodes.get(current)!.parentId; }
    result.reverse();
    return Object.freeze(result);
  }

  subtreeSize(id: string): number { return this.#require(id).subtreeSize; }

  preorder(id = this.#rootId): readonly string[] {
    this.#require(id);
    const output: string[] = [];
    const stack = [id];
    while (stack.length > 0) {
      const current = stack.pop()!; output.push(current);
      const children = [...this.#nodes.get(current)!.children].sort((a, b) => b.localeCompare(a));
      stack.push(...children); // 逆序压入，弹出时字典序升序
    }
    return Object.freeze(output);
  }

  moveSubtree(id: string, newParentId: string): void {
    const node = this.#require(id);
    const newParent = this.#require(newParentId);
    if (id === this.#rootId) throw new Error("cannot move root");
    if (id === newParentId) throw new Error("cannot parent a node to itself");
    let cursor: string | null = newParentId;
    while (cursor !== null) {
      if (cursor === id) throw new Error("move would create a cycle");
      cursor = this.#nodes.get(cursor)!.parentId;
    }
    const oldParentId = node.parentId!;
    if (oldParentId === newParentId) return;

    const size = node.subtreeSize;
    this.#nodes.get(oldParentId)!.children.delete(id);
    newParent.children.add(id);
    node.parentId = newParentId;
    this.#adjustAncestors(oldParentId, -size);
    this.#adjustAncestors(newParentId, size);
  }

  #adjustAncestors(start: string, delta: number): void {
    let current: string | null = start;
    while (current !== null) {
      const currentNode: OrgNode = this.#nodes.get(current)!;
      currentNode.subtreeSize += delta;
      current = currentNode.parentId;
    }
  }
  #require(id: string): OrgNode {
    const node = this.#nodes.get(id);
    if (node === undefined) throw new Error(`unknown org node: ${id}`);
    return node;
  }
}
```

### 正确性和复杂度

构造先完成所有局部验证，再从唯一 root 遍历。每个非根只有一个 parent；若 root 遍历访问所有节点且未重复，就得到一棵连通无环树。exiting 帧保证子节点 size 已算完再计算父。

move 的所有可能失败在 mutation 前检查。新父不是 node 子树内时，换边不会成环且仍保持每个非根一个 parent。旧祖先减 size、新祖先加 size；共同祖先净变化 0，其他祖先恰好反映成员变化。

构造/全遍历 O(n)，空间 O(n)；ancestors/move O(height)，preorder O(subtreeSize + 兄弟排序成本)。当前 children 是 Set，每次遍历排序；若读多写少可缓存排序数组，代价是写时维护另一不变量。

构造失败时对象不会返回给调用者，因此内部已局部挂边不造成可观察半状态。move 中内置 Set 操作在正常内存条件下同步完成；若需要崩溃/并发原子性，必须在数据库事务里验证版本和防环，不能依赖此对象。

复写任务：实现 `assertSubtreeSizesSlow()`，迭代后序重算所有 size；随机生成小树并做合法 move，每次与缓存比较。再加入一个不合法 move，序列化 preorder/ancestors/sizes 前后应完全一致。
