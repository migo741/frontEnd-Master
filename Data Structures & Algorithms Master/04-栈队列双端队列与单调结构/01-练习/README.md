# 第 04 章练习

## 练习 1：从零实现泛型 Deque（经典机制）

```ts
export declare class ArrayDeque<T> implements Iterable<T> {
  constructor(initialCapacity?: number);
  get size(): number;
  pushFront(value: T): void;
  pushBack(value: T): void;
  popFront(): T | undefined;
  popBack(): T | undefined;
  peekFront(): T | undefined;
  peekBack(): T | undefined;
  [Symbol.iterator](): Iterator<T>;
}
```

要求：循环数组实现，不得用 `shift/unshift/splice`；容量不足时几何扩容；删除后清空槽位；两端操作摊还 O(1)；迭代器采用 fail-fast——创建迭代器后若结构发生修改，下一次 `next()` 抛错。初始容量至少 1，拒绝非正整数。

交付：不变量说明、逻辑下标到物理下标公式、扩容状态图。用普通数组做 oracle，固定 seed 随机执行至少 50,000 次混合操作；初始容量设为 1，强制覆盖绕回和多次扩容。

发散：是否自动缩容？若缩容，怎样避免 size 在阈值附近抖动导致反复复制？为什么允许存 `undefined` 时当前返回类型无法区分空？

## 练习 2：有界遥测缓冲区（生产/开放）

设计一个单进程浏览器遥测缓冲。事件有严格递增 sequence、已经计算好的 UTF-8 `byteSize`，优先级为 `critical | bestEffort`。

必须满足：

- `bufferedBytes + reservedBytes <= maxBytes` 永远成立；
- best-effort 空间不足时拒绝新项；critical 到达时先淘汰最旧 best-effort，再在必要时淘汰最旧 critical；仍放不下则拒绝；所有丢弃计入指标；
- drain 按全局 sequence 顺序，使用 lease；同一时刻只允许一个 lease；成功 commit，失败 rollback；重复 finalize 抛错；
- in-flight reserved 容量不能被新事件占用，rollback 后仍保持顺序；
- 单项大于 maxBytes、重复/倒序 sequence、非法 byteSize 在改变状态前拒绝。

你可设计具体类型，但必须提供：append、beginDrain、stats、lease.commit/rollback。不得无限保存每个 dropped sequence；指标内存也必须有界。

测试：fake flush 下穿插 append/rollback；每一步检查容量不变量；验证两类队列合并后的 sequence 全序；对 maxBytes=1、事件恰好填满、在途占满等边界做定向测试。

发散：页面崩溃/刷新如何恢复？多 tab 同时上报怎样协调？如果 critical 法规审计事件绝对不能丢，架构必须怎样改变？
