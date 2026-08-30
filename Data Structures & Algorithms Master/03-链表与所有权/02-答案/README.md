# 第 03 章参考答案

## 题 1：原地反转单向链表

### 1. 先写契约

函数得到这条链的独占修改权，并假定它最终到达 `null`。如果输入成环，循环不会终止；如果调用方仍把旧链接关系当成有效，反转后会观察到完全不同的结构。这些都不是类型签名能自动保证的事实，必须写入 API 文档并在可信边界处理。

```ts
export interface ListNode<T> {
  value: T;
  next: ListNode<T> | null;
}

export function reverseInPlace<T>(
  head: ListNode<T> | null,
): ListNode<T> | null {
  let previous: ListNode<T> | null = null;
  let current = head;

  while (current !== null) {
    const next = current.next;
    current.next = previous;
    previous = current;
    current = next;
  }
  return previous;
}
```

### 2. 状态追踪

对 `A -> B -> C -> null`：

| 轮次 | `previous` 所在反转前缀 | `current` 所在待处理后缀 | 保存的 `next` |
|---:|---|---|---|
| 初始 | `null` | `A -> B -> C` | 尚未读取 |
| 1 后 | `A -> null` | `B -> C` | B |
| 2 后 | `B -> A -> null` | `C` | C |
| 3 后 | `C -> B -> A -> null` | `null` | null |

循环不变量是：原链的节点被恰好分成两个不重叠区域；`previous` 包含已经反向连接的前缀，`current` 包含仍保持原方向的后缀，合起来没有丢节点或新增节点。

初始化时前缀为空，不变量成立。每轮在覆盖 `current.next` 前保存后缀入口，再把 current 从后缀移到前缀，因此保持。每轮待处理节点数减 1；有限无环链必终止。终止时后缀为空，全部节点都在 previous 中且方向已反转，所以 previous 是新头。

时间 `O(n)`，每节点访问一次；辅助空间 `O(1)`，只保存三个引用。

### 3. 测试引用身份，而不只是值

```ts
import { describe, expect, it } from "vitest";

it("reuses every original node", () => {
  const c: ListNode<string> = { value: "C", next: null };
  const b: ListNode<string> = { value: "B", next: c };
  const a: ListNode<string> = { value: "A", next: b };

  const result = reverseInPlace(a);
  expect(result).toBe(c);
  expect(c.next).toBe(b);
  expect(b.next).toBe(a);
  expect(a.next).toBeNull();
});

it("handles empty and singleton lists", () => {
  expect(reverseInPlace(null)).toBeNull();
  const one: ListNode<number> = { value: 1, next: null };
  expect(reverseInPlace(one)).toBe(one);
  expect(one.next).toBeNull();
});
```

测试 100,000 节点时应迭代构造和计数；若测试辅助函数本身用递归，也会产生与被测代码无关的栈溢出。

### 4. 常见错误的最小反例

若先执行 `current.next = previous`，再读取 `current.next` 作为下一节点，从 `A -> B` 开始第一轮就会把 `A.next` 改为 null，然后把 current 设为 null，B 永久丢失。最小失败输入只需两个节点。

## 题 2：可取消任务队列

### 1. 为什么必须有私有节点身份

若 `cancel` 只按 value 删除，重复值无法定位；若从 head 扫描 handle，取消是 `O(n)`；若把可写 `prev/next` 暴露给调用者，调用者能破坏结构。

答案让 handle 是内部类实例，并用模块私有 `unique symbol` 关联节点。公共类型只暴露只读 value；外部普通对象即使形状相同，也不能通过运行时 `instanceof` 检查。每个队列还有唯一 owner token，防止另一队列取消本队列节点。

```ts
export interface TaskHandle<T> {
  readonly value: T;
}

const HANDLE_NODE: unique symbol = Symbol("queue-handle-node");

interface QueueNode<T> {
  value: T | undefined;
  prev: QueueNode<T> | null;
  next: QueueNode<T> | null;
  owner: object | null;
  linked: boolean;
}

class InternalTaskHandle<T> implements TaskHandle<T> {
  public readonly [HANDLE_NODE]: QueueNode<T>;
  constructor(public readonly value: T, node: QueueNode<T>) {
    this[HANDLE_NODE] = node;
  }
}

export class CancellableTaskQueue<T> {
  readonly #owner = Object.freeze({});
  #head: QueueNode<T> | null = null;
  #tail: QueueNode<T> | null = null;
  #size = 0;

  get size(): number {
    return this.#size;
  }

  enqueue(value: T): TaskHandle<T> {
    const node: QueueNode<T> = {
      value,
      prev: this.#tail,
      next: null,
      owner: this.#owner,
      linked: true,
    };

    if (this.#tail === null) {
      this.#head = node;
    } else {
      this.#tail.next = node;
    }
    this.#tail = node;
    this.#size += 1;
    return new InternalTaskHandle(value, node);
  }

  peek(): T | undefined {
    return this.#head?.value;
  }

  dequeue(): T | undefined {
    if (this.#head === null) return undefined;
    const node = this.#head;
    const value = node.value;
    this.#unlink(node);
    return value;
  }

  cancel(handle: TaskHandle<T>): boolean {
    if (!(handle instanceof InternalTaskHandle)) return false;
    const node = (handle as InternalTaskHandle<T>)[HANDLE_NODE];
    if (!node.linked || node.owner !== this.#owner) return false;
    this.#unlink(node);
    return true;
  }

  #unlink(node: QueueNode<T>): void {
    // 只有本类在 owner/linked 验证后调用。
    const { prev, next } = node;
    if (prev === null) this.#head = next;
    else prev.next = next;

    if (next === null) this.#tail = prev;
    else next.prev = prev;

    node.prev = null;
    node.next = null;
    node.owner = null;
    node.linked = false;
    node.value = undefined; // 队列释放 payload；调用方自己的 handle 仍可能持有 value。
    this.#size -= 1;
  }
}
```

### 2. 不变量为什么保持

- enqueue 前若为空，head/tail 同时指向新节点；若非空，旧 tail.next 与新节点.prev 对称更新。
- unlink 对前驱、后继各更新一次；缺少前驱意味着删 head，缺少后继意味着删 tail。
- 只有 owner 匹配且 linked 的节点可进入 unlink，所以 size 只减一次，跨队列或 stale handle 不生效。
- 删除后清空链接、owner 与 linked。句柄仍指向节点对象，但无法再通过它修改队列。

每个公共操作只读写固定数量的引用，所以 enqueue、peek、dequeue、cancel 都是 `O(1)`；每个任务一个节点与 handle，空间 `O(n)`。

### 3. 测试矩阵

```ts
it("cancels the exact duplicate-valued task", () => {
  const q = new CancellableTaskQueue<string>();
  const first = q.enqueue("same");
  const middle = q.enqueue("same");
  q.enqueue("last");

  expect(q.cancel(middle)).toBe(true);
  expect(q.cancel(middle)).toBe(false);
  expect(q.size).toBe(2);
  expect(q.dequeue()).toBe("same");
  expect(q.dequeue()).toBe("last");
  expect(q.cancel(first)).toBe(false); // 已出队
});

it("rejects foreign and forged handles", () => {
  const a = new CancellableTaskQueue<number>();
  const b = new CancellableTaskQueue<number>();
  const handle = a.enqueue(1);
  expect(b.cancel(handle)).toBe(false);
  expect(a.cancel({ value: 1 })).toBe(false);
  expect(a.size).toBe(1);
});
```

再分别覆盖删唯一节点、头、中、尾以及交替 enqueue/dequeue。测试环境可以增加一个仅测试可用的 `assertInvariants()`：从 head 前向计数、检查 prev/next 对称、到达 tail 且数量等于 size；但不要把遍历放入每次生产操作，否则会把 `O(1)` 变成 `O(n)`。

### 4. 生命周期与并发边界

`node.value = undefined` 解除队列对 payload 的引用，但 handle 自己承诺暴露 value，所以调用方若长期保存 handle，payload 仍可达。这不是队列能偷偷解决的问题；大型 payload 可改为只在 handle 中保存 task ID，或提供显式 `dispose()` 契约。

单个 JavaScript agent 内，同步 `cancel` 与 `dequeue` 不会在一条语句中间被另一个回调抢占，因此先执行者获胜，后执行者看到 linked=false。若工作已经 dequeue，取消返回 false。若要表达“已开始但仍可协作取消”，任务本身应接收 `AbortSignal`，这与从等待队列移除是两种状态。

Worker/多线程之间不能共享普通对象引用链并期望原子更新。真正跨线程/进程队列需要消息传递，或基于 SharedArrayBuffer/Atomics 的专门协议；持久任务还需要数据库/消息队列的确认、租约、幂等和恢复。本题是单进程内存结构，不能冒充生产分布式任务系统。

### 5. 复写与发散

关掉答案，从五条不变量重新写 `#unlink`，不要背字段更新顺序。然后加入 `moveToBack(handle)`：仍要求 `O(1)`、失效 handle 返回 false。说明如何在不改变 size 的前提下先摘除再挂到尾部，并为单节点情况写测试。
