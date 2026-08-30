# 第 01 章参考答案

## 题 1：动态数组与摊还分析

### 1. 实现

```ts
export class GeometricArray<T> {
  #storage: Array<T | undefined>;
  #length = 0;
  #copied = 0;

  constructor(initialCapacity = 1) {
    if (!Number.isSafeInteger(initialCapacity) || initialCapacity <= 0) {
      throw new RangeError("initialCapacity must be a positive safe integer");
    }
    this.#storage = new Array<T | undefined>(initialCapacity);
  }

  get length(): number { return this.#length; }
  get capacity(): number { return this.#storage.length; }
  get copiedElements(): number { return this.#copied; }

  get(index: number): T {
    this.#checkIndex(index);
    return this.#storage[index] as T;
  }

  set(index: number, value: T): void {
    this.#checkIndex(index);
    this.#storage[index] = value;
  }

  push(value: T): void {
    if (this.#length === this.#storage.length) this.#grow();
    this.#storage[this.#length] = value;
    this.#length += 1;
  }

  pop(): T | undefined {
    if (this.#length === 0) return undefined;
    const index = this.#length - 1;
    const value = this.#storage[index];
    this.#storage[index] = undefined;
    this.#length = index;
    return value;
  }

  #grow(): void {
    const nextCapacity = this.#storage.length * 2;
    if (!Number.isSafeInteger(nextCapacity)) throw new RangeError("capacity overflow");
    const next = new Array<T | undefined>(nextCapacity);
    for (let i = 0; i < this.#length; i += 1) {
      next[i] = this.#storage[i];
      this.#copied += 1;
    }
    this.#storage = next;
  }

  #checkIndex(index: number): void {
    if (!Number.isSafeInteger(index) || index < 0 || index >= this.#length) {
      throw new RangeError(`index out of range: ${index}`);
    }
  }
}
```

`as T` 的依据不是“相信编译器”，而是不变量保证 `[0,length)` 每个槽位已经由 push/set 写入；T 本身也可能是 undefined。公共 pop 仍无法区分空数组和真实弹出 undefined，关键接口可改成：

```ts
type PopResult<T> = { readonly ok: false } | { readonly ok: true; readonly value: T };
```

### 2. 不变量与正确性

始终保持：`0<=length<=capacity`；逻辑元素恰在 `[0,length)`，顺序与 push 一致；`[length,capacity)` 不属于容器。grow 逐项复制相同下标后只改变容量，不改变逻辑序列；push 在 length 位置写入再加一；pop 先保存最后值、清引用再减一，均保持。

### 3. 为什么翻倍是摊还 O(1)

initialCapacity=1 时，在旧容量 1、2、4、8... 满时复制。插入 n 项前的总复制：

```text
1 + 2 + 4 + ... + 2^k < 2n
```

再加每次写新元素的 n 次常数工作，总工作 <3n 的常数倍，所以 n 次 push O(n)，平均到每次为摊还 O(1)。这不代表触发扩容的某一次不是 O(n)。

若每次只加 1 格，第 i 次扩容复制 i-1 项：

```text
0 + 1 + 2 + ... + (n-1) = n(n-1)/2 = Θ(n²)
```

会计法也可把每次 push 收取固定“代币”，未扩容操作保存代币，下一次扩容用累积代币支付旧元素搬移。

### 4. 测试与生产解释

随机维护 `model: Array<T|undefined>`，操作 push/pop/get/set 后比较 length 与每个逻辑值；容量只断言>=length且为初始容量乘 2 的幂级。copiedElements 对前 16 项应为 `1+2+4+8=15`。

JavaScript Array 本身已经是动态结构；手写类是为了看见扩容成本，不建议替换标准数组。引擎还会根据 elements kind、稀疏度和类型改变内部表示，课程的复制模型是抽象成本，不是 ECMAScript 规定的具体实现。

## 题 2：导入预检

### 1. 先定义慢 oracle

对小输入，慢版可对第 i 行扫描 `0..i-1` 判断重复，再扫描全部 rows/existing 判断 parent。它接近规则文字、便于审查，即使 O(n²) 也适合 n<=200 的随机差分。优化版与它共享输入 validator 会降低独立性；oracle 应尽量直接写规则。

### 2. 两遍索引实现

```ts
interface ImportRow {
  readonly rowNumber: number; readonly externalId: string;
  readonly parentExternalId: string | null; readonly amountCents: number;
}
type IssueCode = "INVALID_ROW_NUMBER" | "INVALID_ID" | "INVALID_AMOUNT"
  | "DUPLICATE_ID" | "SELF_PARENT" | "UNKNOWN_PARENT";
interface ImportIssue { readonly rowNumber: number; readonly code: IssueCode; readonly detail: string }

const CODE_ORDER: Readonly<Record<IssueCode, number>> = {
  INVALID_ROW_NUMBER: 0, INVALID_ID: 1, INVALID_AMOUNT: 2,
  DUPLICATE_ID: 3, SELF_PARENT: 4, UNKNOWN_PARENT: 5,
};

export function validateImport(
  rows: readonly ImportRow[],
  existingIds: ReadonlySet<string>,
  limits: { readonly maxRows: number; readonly maxIdCodeUnits: number },
): readonly ImportIssue[] {
  if (!Number.isSafeInteger(limits.maxRows) || limits.maxRows < 0
      || !Number.isSafeInteger(limits.maxIdCodeUnits) || limits.maxIdCodeUnits <= 0) {
    throw new RangeError("invalid import limits");
  }
  if (rows.length > limits.maxRows) throw new RangeError(`row limit exceeded: ${rows.length}`);

  const issues: ImportIssue[] = [];
  const validBatchIds = new Set<string>();
  const validIdByIndex = new Array<string | null>(rows.length).fill(null);
  const add = (rowNumber: number, code: IssueCode, detail: string): void => {
    issues.push({ rowNumber, code, detail });
  };

  // 第一遍建立完整 batch ID 集，使 parent 可以出现在当前行之后。
  rows.forEach((row, index) => {
    const reportRow = Number.isSafeInteger(row.rowNumber) ? row.rowNumber : Number.MAX_SAFE_INTEGER;
    if (!Number.isSafeInteger(row.rowNumber) || row.rowNumber <= 0) {
      add(reportRow, "INVALID_ROW_NUMBER", String(row.rowNumber));
    }
    if (!Number.isSafeInteger(row.amountCents) || row.amountCents < 0) {
      add(reportRow, "INVALID_AMOUNT", String(row.amountCents));
    }
    const idValid = typeof row.externalId === "string"
      && row.externalId.length > 0
      && row.externalId.length <= limits.maxIdCodeUnits
      && row.externalId === row.externalId.trim();
    if (!idValid) {
      add(reportRow, "INVALID_ID", "externalId must be non-empty, bounded and trimmed");
      return;
    }
    validIdByIndex[index] = row.externalId;
    if (validBatchIds.has(row.externalId)) {
      add(reportRow, "DUPLICATE_ID", row.externalId);
    } else {
      validBatchIds.add(row.externalId);
    }
  });

  // 第二遍检查需要完整 ID 集才能判断的父引用。
  rows.forEach((row, index) => {
    if (row.parentExternalId === null) return;
    const reportRow = Number.isSafeInteger(row.rowNumber) ? row.rowNumber : Number.MAX_SAFE_INTEGER;
    const ownId = validIdByIndex[index];
    const parent = row.parentExternalId;
    const parentShapeValid = typeof parent === "string" && parent.length > 0
      && parent.length <= limits.maxIdCodeUnits && parent === parent.trim();
    if (!parentShapeValid) {
      add(reportRow, "UNKNOWN_PARENT", String(parent));
    } else if (ownId !== null && parent === ownId) {
      add(reportRow, "SELF_PARENT", parent);
    } else if (!validBatchIds.has(parent) && !existingIds.has(parent)) {
      add(reportRow, "UNKNOWN_PARENT", parent);
    }
  });

  issues.sort((a, b) =>
    a.rowNumber - b.rowNumber
      || CODE_ORDER[a.code] - CODE_ORDER[b.code]
      || a.detail.localeCompare(b.detail),
  );
  return Object.freeze(issues.map((issue) => Object.freeze(issue)));
}
```

### 3. 正确性与复杂度

第一遍后，validBatchIds 恰含所有形状合法 ID；重复项只影响 issue，不移除第一项。第二遍因此能判断位于后面的 parent。每条规则产生独立 issue，最终统一全序，输入/Map 迭代不会改变结果。

两遍扫描 O(n)，Set 查询在常见实现假设下期望 O(1)，issue 排序 O(i log i)，额外空间 O(n+i)（existingIds 由调用方提供，不计新分配）。字符串 trim/长度与 detail 排序仍有字符长度成本；若 ID 长度已受 L 限制，可写入 O(nL+i log i·L)。

### 4. benchmark 与边界

生成固定 seed 的有效、重复、未知父混合数据，先 warm-up；对 n=1k、2k、4k... 取至少 5 次中位数，慢版只跑到安全规模。记录 Node/浏览器版本、硬件、GC策略和峰值 heap。看倍增比：线性算法 n 翻倍接近常数倍，O(n²) 接近四倍，但不要把噪声当证明。

百万行仍可能因整批对象和 issue 占巨大内存。真实 CSV 应流式解析到 staging table/临时文件：第一遍规范化并建立唯一索引，第二遍 join 检查 parent，数据库唯一/外键或 SQL anti-join 往往更合适。多租户 ID 要把 tenant 放进键；外部攻击输入需限制行数、字段长度、总字节、解析时间和错误数（例如达到 10k issue 后截断并报告）。

复写任务：给 errors 加 `maxIssues`，要求一旦截断仍返回 `{truncated:true}` 且不谎称剩余数据有效。先写契约，再决定是停止全部验证还是只停止收集 detail。

