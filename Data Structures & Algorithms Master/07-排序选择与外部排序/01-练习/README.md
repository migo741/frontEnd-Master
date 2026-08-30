# 第 07 章练习

本章恰好两题。第一题练习“不完整排序也能定位第 k 项”；第二题模拟外部排序的 k 路流式归并。

## 练习 1：泛型三路 Quickselect

### 场景

监控服务一次收到一批延迟样本，只需要精确中位数或第 k 小值，不需要完整排序。样本中可能有大量重复值。

实现：

~~~ts
export interface SelectOptions {
  readonly random?: () => number;
}

export declare function selectKth<T>(
  values: readonly T[],
  k: number,
  compare: (left: T, right: T) => number,
  options?: SelectOptions,
): T;
~~~

### 约定与要求

- k 是从 0 开始的升序排名。
- 空输入、越界 k、random 返回非有限值或不在 <code>[0, 1)</code> 时抛出明确错误。
- 不得修改输入；可以复制一份工作数组。
- 必须使用随机 pivot 与三路分区，正确处理大量重复值。
- 不得调用 <code>sort()</code> 或 <code>toSorted()</code>。
- 比较器判等只意味着排序等价，不要求对象引用相同。

### 必测情况

- 单元素、已排序、逆序、全相等、大量重复值。
- 对象数组和自定义比较器。
- k 为 0 和最后一个位置。
- 注入确定的伪随机函数，使测试可重复。
- 随机生成小数组，与完整排序结果做差分测试。

### 需要说明

- 三路分区四段不变量。
- 为什么期望时间为 <code>O(n)</code>，最坏仍为 <code>O(n²)</code>。
- 复制输入带来的时间和空间成本。
- 若服务对最坏尾延迟有硬限制，你会换什么方案？

## 练习 2：有界内存的异步 k 路归并

### 场景

外部排序已经生成多个有序运行段。每个运行段可能来自文件、对象存储或数据库游标，因此以 <code>AsyncIterable</code> 暴露。请在不把全部数据读入内存的前提下，合并为一个有序输出流。

~~~ts
export interface MergeOptions {
  readonly validateSourceOrder?: boolean;
}

export declare function mergeSortedSources<T>(
  sources: readonly AsyncIterable<T>[],
  compare: (left: T, right: T) => number,
  options?: MergeOptions,
): AsyncGenerator<T, void, void>;
~~~

### 要求

- 内存中每个输入源最多保留一个当前元素，加上 <code>O(k)</code> 的堆状态。
- 总输出按 compare 非降序。
- 比较相等时，较小 source 下标优先，保证确定性；每个源内部顺序不变。
- 开启 <code>validateSourceOrder</code> 时，如果任一源自身降序，抛出明确错误。
- 任一源读取失败时传播错误。
- 消费者提前停止或发生错误时，尽力调用所有输入迭代器的 <code>return()</code>。
- 不得用每次线性扫描所有源头的 <code>O(nk)</code> 方案。

### 开放设计问题

1. k 大于操作系统文件描述符上限时如何多轮归并？
2. 如何加入输入/输出缓冲、检查点和临时文件清理？
3. 一个源长期变慢时，严格全局排序为什么会产生队头阻塞？
4. 若只需要全局前 1,000 项，消费者提前停止如何减少 I/O？

### 验收标准

- 空 sources、空源混合、重复键、单源和多源均正确。
- 有序性验证能定位具体 source。
- 使用可观察的假迭代器验证提前停止调用了 return。
- 写出 <code>n</code> 个总元素、<code>k</code> 个源时的时间和空间复杂度。
