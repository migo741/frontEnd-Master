# 第 09 章练习

## 练习 1：AVL OrderedSet（经典机制）

```ts
type Comparator<T> = (a: T, b: T) => number;

declare class AvlOrderedSet<T> implements Iterable<T> {
  constructor(compare: Comparator<T>);
  get size(): number;
  has(value: T): boolean;
  add(value: T): boolean; // 新增 true，比较相等则 false
  [Symbol.iterator](): Iterator<T>; // 中序
}
```

实现 insert/search、LL/RR/LR/RL 旋转、height 更新；不要求 delete。空高度 0、叶高度 1。不得用 sort/Map 代替树核心。

交付测试专用 `assertInvariants`：检查严格 BST 范围、缓存 height、每节点平衡因子和节点数。分别构造四种旋转；固定 seed 随机插入后与 Set+排序 oracle 比较；升序插入 10,000 项，验证高度不超过一个保守对数上界。

## 练习 2：组织树索引与原子移动（生产/开放）

```ts
interface OrgRow { readonly id: string; readonly parentId: string | null }

declare class OrganizationTreeIndex {
  constructor(rows: readonly OrgRow[]);
  get rootId(): string;
  ancestors(id: string): readonly string[]; // root 到直接父
  subtreeSize(id: string): number;
  preorder(id?: string): readonly string[];
  moveSubtree(id: string, newParentId: string): void;
}
```

契约：恰好一个 root；拒绝重复、空 ID、未知 parent、self-parent、多根和任意环；无序 rows 合法。children 以 ID 字典序遍历，输出确定。move 不能移动 root，不能移到自身/后代；所有验证发生在 mutation 前；成功后维护 parent/children/subtreeSize。深度 100,000 的链构造、遍历和 ancestors 不得依赖递归。

交付：慢速全量 size 重算 oracle；每次随机合法 move 后对比；失败 move 前后快照相等。

发散：多人并发移动怎样用数据库版本/事务处理？兄弟有 position 时如何稳定重排？组织图允许一人多经理后，为什么它不再是树？
