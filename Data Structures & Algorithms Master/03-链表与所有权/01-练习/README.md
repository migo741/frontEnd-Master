# 第 03 章练习

本章恰好两题。编码前先画指针图；答案正确但无法说明所有权和失效规则，视为未完成。

## 练习 1：原地反转单向链表

### 场景

实现链式处理管线的方向反转。函数获得一条无环单链表的独占修改权，必须复用原节点返回反转后的新头。

### 类型与接口

```ts
export interface ListNode<T> {
  value: T;
  next: ListNode<T> | null;
}

export declare function reverseInPlace<T>(
  head: ListNode<T> | null,
): ListNode<T> | null;
```

### 要求

- 不创建新链表节点，不把节点收集到数组中。
- 不使用递归，避免长链调用栈溢出。
- 返回新 head；原 head 反转后应成为 tail，且 `next === null`。
- 输入为空或单节点时行为正确。
- 前置条件是输入无环且调用方授予独占修改权；在说明中写清违反条件的后果。

### 验收标准

- 时间 `O(n)`、辅助空间 `O(1)`。
- 写出“已反转前缀 + 未处理后缀”的循环不变量。
- 测试不仅比较 value 顺序，还要验证每个返回节点与原节点引用相同。
- 对 100,000 个节点的链不会因为递归栈溢出。

## 练习 2：可取消任务队列

### 场景

前端调度器按 FIFO 执行后台任务，但任务在执行前可能通过稳定 handle 被取消。取消头部、中间或尾部任务都必须是 `O(1)`，且不能扫描数组。

### 公共接口

```ts
export interface TaskHandle<T> {
  readonly value: T;
}

export declare class CancellableTaskQueue<T> {
  readonly size: number;

  enqueue(value: T): TaskHandle<T>;
  peek(): T | undefined;
  dequeue(): T | undefined;
  cancel(handle: TaskHandle<T>): boolean;
}
```

### 语义

- `enqueue` 把任务放到尾部并返回只读、稳定的 handle。
- `dequeue` 移除并返回队首，空队列返回 `undefined`。
- `cancel` 仅在 handle 当前属于本队列且仍挂载时移除并返回 `true`。
- 已取消、已出队、来自另一队列或伪造的 handle，`cancel` 返回 `false`，不得破坏 size 和链接。
- FIFO 顺序稳定；值重复不影响基于 handle 的精确取消。
- 不使用数组扫描、`Map` 或 `Set` 反查节点。内部应以双向链表和 owner 身份完成。

### 开放设计问题

说明 handle 的运行时封装边界、任务 payload 释放、同一任务在取消与执行竞争时的语义。如果真正存在 Worker/多线程并发，指出为什么普通 JavaScript 对象链表不能提供跨线程原子性。

### 验收标准

- enqueue、peek、dequeue、cancel 均为 `O(1)`。
- 始终满足 head/tail/prev/next/size/owner/linked 不变量。
- 覆盖空队列、单节点、取消头/中/尾、重复取消、跨队列取消、重复 value。
- 删除后清理节点链接和 owner，避免 stale handle 再次修改结构。
