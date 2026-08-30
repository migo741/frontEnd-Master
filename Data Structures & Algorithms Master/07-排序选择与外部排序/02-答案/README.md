# 第 07 章答案

## 练习 1 答案：泛型三路 Quickselect

### 1. 建模

我们只关心排序后下标 k 的元素，不需要让其他位置全部有序。一次三路分区会得到：

~~~text
[left, less)       < pivot
[less, scan)       == pivot
[scan, greater]    未分类
(greater, right]   > pivot
~~~

当未分类区为空：

- k 小于 less，只保留左区；
- k 大于 greater，只保留右区；
- 否则 k 落在等值区，pivot 即答案。

### 2. 朴素方案与瓶颈

复制并完整排序最简单，时间 <code>O(n log n)</code>。对于一次性、小数组，它可能是工程上更好的选择；但本题目的是掌握只处理相关分区的选择算法。

固定选首项作 pivot 会让有序输入反复只排除一个元素。随机 pivot 让输入排列与 pivot 位置解耦，但仍只有期望保证。

### 3. 参考实现

~~~ts
export interface SelectOptions {
  readonly random?: () => number;
}

function swap<T>(values: T[], left: number, right: number): void {
  const temporary = values[left];
  values[left] = values[right];
  values[right] = temporary;
}

export function selectKth<T>(
  values: readonly T[],
  k: number,
  compare: (left: T, right: T) => number,
  options: SelectOptions = {},
): T {
  if (!Number.isSafeInteger(k) || k < 0 || k >= values.length) {
    throw new RangeError("k must be a valid zero-based index");
  }

  const random = options.random ?? Math.random;
  const work = values.slice();
  let left = 0;
  let right = work.length - 1;

  while (left <= right) {
    if (left === right) return work[left];

    const sample = random();
    if (!Number.isFinite(sample) || sample < 0 || sample >= 1) {
      throw new RangeError("random() must return a finite value in [0, 1)");
    }

    const pivotIndex = left + Math.floor(sample * (right - left + 1));
    const pivot = work[pivotIndex];

    let less = left;
    let scan = left;
    let greater = right;

    while (scan <= greater) {
      const relation = compare(work[scan], pivot);
      if (Number.isNaN(relation)) {
        throw new TypeError("compare() must not return NaN");
      }

      if (relation < 0) {
        swap(work, less, scan);
        less += 1;
        scan += 1;
      } else if (relation > 0) {
        swap(work, scan, greater);
        greater -= 1;
      } else {
        scan += 1;
      }
    }

    if (k < less) {
      right = less - 1;
    } else if (k > greater) {
      left = greater + 1;
    } else {
      return work[k];
    }
  }

  throw new Error("Quickselect invariant was broken");
}
~~~

### 4. 正确性

分区循环的四段不变量如建模图所示。处理 <code>work[scan]</code>：

- 小于 pivot：交换到 less，less 与 scan 同时前进；
- 大于 pivot：交换到 greater，greater 左移；换来的项尚未分类，所以 scan 不动；
- 等于 pivot：它加入等值区，scan 前进。

循环结束时所有项已分类。目标排名只可能位于包含 k 的分区；排除另外两区不会丢失答案。区间严格缩小，最终会返回。

### 5. 复杂度

- 复制输入：<code>O(n)</code> 时间和 <code>O(n)</code> 空间；
- 随机 pivot 下选择过程期望 <code>O(n)</code> 时间；
- 最坏时间 <code>O(n²)</code>；
- 迭代控制额外空间 <code>O(1)</code>，但连同副本总辅助空间是 <code>O(n)</code>。

若允许修改输入，可去掉副本；API 必须明确这一破坏性行为。硬尾延迟场景可用大小 k 的堆获得 <code>O(n log k)</code> 最坏上界，或直接使用经过验证的库。

### 6. 差分测试

~~~ts
import { expect, it } from "vitest";

function seededRandom(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state * 1664525 + 1013904223) >>> 0;
    return state / 0x1_0000_0000;
  };
}

it("matches a full sort on randomized duplicate-heavy data", () => {
  const generate = seededRandom(7);
  for (let round = 0; round < 500; round += 1) {
    const length = 1 + Math.floor(generate() * 50);
    const input = Array.from(
      { length },
      () => Math.floor(generate() * 9),
    );
    const expected = input.slice().sort((a, b) => a - b);

    for (let k = 0; k < length; k += 1) {
      expect(
        selectKth(input, k, (a, b) => a - b, {
          random: seededRandom(round * 100 + k),
        }),
      ).toBe(expected[k]);
    }
    expect(input).not.toBe(expected);
  }
});
~~~

### 7. 失败边界

本实现无法自动证明比较器传递，也无法限制比较器的执行时间和副作用。对不可信数据，应先做 schema 校验。若数据持续到达或无法装入内存，Quickselect 不合适；使用有界堆、近似分位统计或数据库能力。

## 练习 2 答案：有界内存的异步 k 路归并

### 1. 建模

每个源已经有序，所以全局最小项一定在各源当前头元素之中。用最小堆保存每个非空源的一个头：

1. 弹出最小头并产出；
2. 只从该头所属源读取下一项；
3. 验证源内顺序并把新头压回堆。

比较键相等时用 sourceIndex 打破平局，使结果可重复。

### 2. 朴素方案与瓶颈

把所有源读入数组再 sort 需要 <code>O(n)</code> 内存，违背外部排序目的。每次线性扫描 k 个头虽只用 <code>O(k)</code> 内存，但总时间 <code>O(nk)</code>。最小堆把选择头的成本降为 <code>O(log k)</code>。

### 3. 参考实现

~~~ts
export interface MergeOptions {
  readonly validateSourceOrder?: boolean;
}

interface Head<T> {
  readonly value: T;
  readonly sourceIndex: number;
}

class MinHeap<T> {
  private readonly data: T[] = [];

  public constructor(
    private readonly compare: (left: T, right: T) => number,
  ) {}

  public get size(): number {
    return this.data.length;
  }

  public push(value: T): void {
    this.data.push(value);
    let index = this.data.length - 1;
    while (index > 0) {
      const parent = Math.floor((index - 1) / 2);
      if (this.compare(this.data[parent], value) <= 0) break;
      this.data[index] = this.data[parent];
      index = parent;
    }
    this.data[index] = value;
  }

  public pop(): T | undefined {
    const root = this.data[0];
    const last = this.data.pop();
    if (root === undefined || last === undefined || this.data.length === 0) {
      return root;
    }

    let index = 0;
    while (true) {
      const left = index * 2 + 1;
      if (left >= this.data.length) break;
      const right = left + 1;
      const smaller =
        right < this.data.length &&
        this.compare(this.data[right], this.data[left]) < 0
          ? right
          : left;
      if (this.compare(this.data[smaller], last) >= 0) break;
      this.data[index] = this.data[smaller];
      index = smaller;
    }
    this.data[index] = last;
    return root;
  }
}

export async function* mergeSortedSources<T>(
  sources: readonly AsyncIterable<T>[],
  compare: (left: T, right: T) => number,
  options: MergeOptions = {},
): AsyncGenerator<T, void, void> {
  const iterators = sources.map((source) => source[Symbol.asyncIterator]());
  const previous: Array<T | undefined> = new Array(sources.length);
  const hasPrevious = new Array<boolean>(sources.length).fill(false);

  const compareHead = (left: Head<T>, right: Head<T>): number => {
    const relation = compare(left.value, right.value);
    if (Number.isNaN(relation)) {
      throw new TypeError("compare() must not return NaN");
    }
    return relation || left.sourceIndex - right.sourceIndex;
  };

  const heap = new MinHeap<Head<T>>(compareHead);

  const readNext = async (sourceIndex: number): Promise<void> => {
    const result = await iterators[sourceIndex].next();
    if (result.done === true) return;

    if (
      options.validateSourceOrder === true &&
      hasPrevious[sourceIndex] &&
      compare(previous[sourceIndex] as T, result.value) > 0
    ) {
      throw new TypeError(
        "Source " + String(sourceIndex) + " is not sorted",
      );
    }

    previous[sourceIndex] = result.value;
    hasPrevious[sourceIndex] = true;
    heap.push({ value: result.value, sourceIndex });
  };

  try {
    for (let sourceIndex = 0; sourceIndex < iterators.length; sourceIndex += 1) {
      await readNext(sourceIndex);
    }

    while (heap.size > 0) {
      const head = heap.pop();
      if (head === undefined) {
        throw new Error("Heap invariant was broken");
      }
      yield head.value;
      await readNext(head.sourceIndex);
    }
  } finally {
    await Promise.allSettled(
      iterators.map(async (iterator) => {
        if (iterator.return !== undefined) {
          await iterator.return();
        }
      }),
    );
  }
}
~~~

### 4. 正确性

循环不变量：

1. 每个尚未耗尽的源在堆中恰有一个当前头；
2. 该头之前的项已输出，之后的项不小于该头；
3. 已输出序列有序。

因此所有未输出元素中的最小值必在堆顶。弹出它保持全局顺序；从同源补入下一项后，该源再次满足“不小于已输出项”。重复直到堆空，说明所有源耗尽且无丢失。

相等时 sourceIndex 决定顺序；同一源同一时间只有一个头，因此源内顺序自然保持。

### 5. 复杂度与内存

总元素数 n、源数 k：

- 初始化最多 k 次读取和建堆；
- 每项一次弹出、最多一次压入，时间 <code>O(n log k)</code>；
- 堆、previous、迭代器数组共 <code>O(k)</code>；
- 不包含各数据源自身的 I/O 缓冲。

严格全序意味着在确定下一项前必须等相关最小源的下一头，因此慢源会造成队头阻塞。这不是堆能消除的。

### 6. 测试示例

~~~ts
import { expect, it } from "vitest";

async function* source(values: readonly number[]): AsyncGenerator<number> {
  yield* values;
}

it("merges sorted sources deterministically", async () => {
  const output: number[] = [];
  for await (const value of mergeSortedSources(
    [source([1, 4, 4]), source([1, 3, 9]), source([])],
    (a, b) => a - b,
    { validateSourceOrder: true },
  )) {
    output.push(value);
  }
  expect(output).toEqual([1, 1, 3, 4, 4, 9]);
});

it("rejects an unsorted source", async () => {
  const consume = async (): Promise<void> => {
    for await (const _ of mergeSortedSources(
      [source([1, 5, 2])],
      (a, b) => a - b,
      { validateSourceOrder: true },
    )) {
      // Consume all values.
    }
  };
  await expect(consume()).rejects.toThrow(/Source 0/);
});
~~~

### 7. 失败边界与生产替代

这是归并核心，不是完整外部排序系统。真实实现还要限制同时打开源的数量，设计多轮归并，使用足够大的顺序 I/O 缓冲，记录临时文件清单和校验和，并在崩溃后回收孤儿文件。远程对象存储还涉及重试、范围读取和费用。若数据库已经能用索引执行 <code>ORDER BY</code> 并以游标流式返回，应优先复用数据库，而不是把排序搬到应用层。

