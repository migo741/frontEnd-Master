# 第 01 章练习

本章恰好两题。重点不是记某个算法，而是把成本、不变量和证据写完整。

## 练习 1：可观测的几何扩容数组（经典机制）

实现一个教学用动态数组：

```ts
declare class GeometricArray<T> {
  constructor(initialCapacity?: number);
  get length(): number;
  get capacity(): number;
  get copiedElements(): number;
  get(index: number): T;
  set(index: number, value: T): void;
  push(value: T): void;
  pop(): T | undefined;
}
```

要求：内部用预分配数组与逻辑 length；容量满时翻倍；push 不得调用内部数组的 `push`，扩容逐项复制并累计 `copiedElements`；删除槽位清为 undefined。索引必须是 `[0,length)` 安全整数。初始容量为正安全整数。

交付：

- 写出 `0<=length<=capacity` 与有效槽位不变量；
- 对 initialCapacity=1 连续 push 1、2、4、8、16 项，记录容量和累计复制量；
- 用聚合分析或会计法证明一串 n 次 push 的总成本 O(n)、单次摊还 O(1)；
- 再实现一个“每次满只扩 1 格”的错误版本或成本模拟，说明总复制为何 O(n²)；
- 用普通数组做固定 seed 随机操作 oracle，测试可存 `undefined` 时 pop 返回类型的歧义。

## 练习 2：百万行 CSV 导入预检事故（生产/开放）

旧实现对每行使用 `rows.find(...)` 查重复 ID 和父记录，10,000 行尚可，1,000,000 行超时。请建立慢 oracle，再做线性级优化。

```ts
interface ImportRow {
  readonly rowNumber: number;
  readonly externalId: string;
  readonly parentExternalId: string | null;
  readonly amountCents: number;
}
type IssueCode =
  | "INVALID_ROW_NUMBER"
  | "INVALID_ID"
  | "INVALID_AMOUNT"
  | "DUPLICATE_ID"
  | "SELF_PARENT"
  | "UNKNOWN_PARENT";
interface ImportIssue {
  readonly rowNumber: number;
  readonly code: IssueCode;
  readonly detail: string;
}

declare function validateImport(
  rows: readonly ImportRow[],
  existingIds: ReadonlySet<string>,
  limits: { readonly maxRows: number; readonly maxIdCodeUnits: number },
): readonly ImportIssue[];
```

规则：

- 在任何大分配前检查 `rows.length<=maxRows`；
- rowNumber 必须正安全整数，amountCents 非负安全整数；
- ID 必须非空、长度受限、已 trim；无效 ID 不进入索引；
- 同一有效 externalId 的第一行保留，之后每一行报 DUPLICATE_ID；
- parent 等于自己报 SELF_PARENT；否则 parent 必须在有效 batch ID 或 existingIds 中；
- issue 最终按 rowNumber、固定 code 顺序、detail 排序，不能依赖 Map/Set 迭代偶然顺序；
- 不修改输入，目标 O(n+i log i)（i 为 issue 数；existingIds 由调用方预建。若边扫描边按行输出也可避免最终排序，但需证明顺序）。

交付物：慢速但明显正确的小规模 oracle；优化实现；固定 seed 随机差分；按 n 倍增的 benchmark（预热、重复、取中位数、记录环境和内存）；一份复杂度清单，明确字符串校验/排序也有成本。

发散：如果 rows 是无法回退的异步流，怎样用两遍临时文件/数据库 staging table 处理“父记录可能在后面”？若 ID 由攻击者控制，怎样限制内存和哈希退化？
