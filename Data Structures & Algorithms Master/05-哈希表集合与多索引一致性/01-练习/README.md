# 第 05 章练习

## 练习 1：string-key 开放寻址 HashMap（经典机制）

```ts
export declare class StringHashMap<V> {
  constructor(initialCapacity?: number);
  get size(): number;
  has(key: string): boolean;
  get(key: string): V | undefined;
  set(key: string, value: V): this;
  delete(key: string): boolean;
}
```

要求：线性探测；EMPTY、DELETED、OCCUPIED 三态；容量为 2 的幂且至少 8；负载/used 达阈值时重哈希；删除 tombstone 可复用；相同 key 更新不增加 size；支持存储 `undefined`，因此 has 不能依赖 get；不得用 Map/Object 作为内部存储。

交付：画出三个相同初始桶的 key 插入、删除中间项、继续查找与复用 tombstone；写出探测不变量；通过构造或测试 hook 强制碰撞；用原生 Map 做 100,000 次固定 seed 随机差分。

说明教学 hash 的 Unicode 单位与安全边界，不能宣称可直接暴露给攻击者输入。

## 练习 2：工单多索引（生产/开放）

```ts
type TicketStatus = "open" | "pending" | "closed";
interface Ticket {
  readonly id: string;
  readonly status: TicketStatus;
  readonly assignee: string | null;
  readonly title: string;
}

interface TicketQuery {
  readonly status?: TicketStatus;
  readonly assignee?: string | null;
}
```

实现 `TicketIndex.insert/update/delete/get/query`：主索引 id，二级索引 status 与 assignee。拒绝重复/空 ID、非法状态和不存在更新。query 不得扫描全主表；若同时给两个条件，从较小桶迭代并在另一桶做成员检查；结果按 id 稳定排序且返回只读快照。

写操作必须先验证，再以 undo journal 维护原子可见状态；提供测试用 fault injector，在每个提交步骤前抛错，状态应恢复到操作前。每次测试写后运行全量 `assertInvariants()`。

发散：

1. 一个 status 桶包含千万 ID 时，复制返回和排序成本怎样处理？
2. 多字段任意组合查询会导致多少索引？何时交给数据库？
3. 多进程同时更新同一 ticket 时，为什么本类的 journal 无效？
4. 二级索引异步构建时怎样表示 ready/version，避免读到混合版本？
