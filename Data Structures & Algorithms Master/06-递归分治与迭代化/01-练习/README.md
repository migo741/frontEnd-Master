# 第 06 章练习

本章恰好两题。练习 1 聚焦递归契约与显式栈；练习 2 把它放进可能超深、可取消、需要让出事件循环的生产导入场景。

## 练习 1：安全求值规则表达式树

### 场景

一个 SaaS 权限系统把布尔规则保存为对象树。规则只允许常量、逻辑非、逻辑与和逻辑或，不允许使用 <code>eval</code>。配置可能由用户或旧系统生成，因此不能假定深度合理，也不能假定对象引用绝对无环。

~~~ts
export type Rule =
  | { readonly kind: "literal"; readonly value: boolean }
  | { readonly kind: "not"; readonly child: Rule }
  | { readonly kind: "and"; readonly children: readonly Rule[] }
  | { readonly kind: "or"; readonly children: readonly Rule[] };

export interface EvaluateOptions {
  readonly maxDepth: number;
  readonly maxNodes: number;
}

export declare function evaluateRule(
  root: Rule,
  options: EvaluateOptions,
): boolean;
~~~

### 要求

- 必须使用显式栈，不得依赖递归。
- 保持正常布尔语义：空 <code>and</code> 为 <code>true</code>，空 <code>or</code> 为 <code>false</code>。
- 对 <code>and</code> 和 <code>or</code>实现短路：一旦结果确定，不再求值剩余孩子。
- 使用对象身份检测当前路径上的引用环。
- 深度超过 <code>maxDepth</code>、访问节点数超过 <code>maxNodes</code> 时抛出明确错误。
- 非法预算、未知 <code>kind</code> 也要有明确失败行为。
- 不得修改输入规则。

### 必测情况

- 单个 literal、not 嵌套、空 and、空 or。
- 多层 and/or，验证短路后未访问的分支不计入节点预算。
- 构造深度 50,000 的 not 链，在足够预算下不发生调用栈溢出。
- 用类型断言构造对象引用环，应被拒绝。
- 恰好等于预算时成功，超过一个时失败。

### 需要写出的说明

- 每种栈帧保存了递归版本的哪些局部变量。
- 栈中正在处理的路径和 <code>active</code> 集合之间的不变量。
- 时间、显式栈空间的上界，以及短路对实际访问量的影响。

## 练习 2：可取消、分批让出执行权的层级数据导入器

### 场景

管理后台允许导入大型组织树。导入前要按前序顺序生成扁平记录，记录每个节点的路径和深度。真实数据可能有几十万节点；如果一次同步遍历，会让 Node.js 服务或浏览器页面长时间无响应。

~~~ts
export interface ImportNode {
  readonly id: string;
  readonly children: readonly ImportNode[];
}

export interface FlatRecord {
  readonly id: string;
  readonly depth: number;
  readonly path: readonly string[];
}

export interface WalkOptions {
  readonly batchSize: number;
  readonly maxDepth: number;
  readonly maxNodes: number;
  readonly signal?: AbortSignal;
  readonly yieldControl: () => Promise<void>;
}

export declare function walkInBatches(
  roots: readonly ImportNode[],
  options: WalkOptions,
): AsyncGenerator<FlatRecord, void, void>;
~~~

### 要求

- 使用显式栈，按 roots 顺序、同级 children 顺序进行前序遍历。
- 每产出 <code>batchSize</code> 条后调用一次 <code>yieldControl()</code>；不要把平台相关的 <code>setImmediate</code> 写死在算法中。
- 支持 <code>AbortSignal</code>；取消后尽快抛出 <code>AbortError</code>。
- 检测对象引用环，并拒绝重复业务 ID。
- 限制最大深度和最大节点数，不得修改输入。
- 路径结果不能在后续遍历中被悄悄改变。
- 消费者提前停止迭代时，不应继续后台工作。

### 开放设计问题

完成实现后讨论：

1. 每个结果都复制完整 path 可能导致多大总内存/时间成本？如果节点很多且很深，可提供什么替代 API？
2. 如果两个父节点合法共享同一个只读子对象，“检测环”和“拒绝共享”应怎样分离？
3. 如果导入需要写数据库，怎样把算法的 batch 与数据库事务、幂等键、失败重试对齐？
4. CPU 工作非常重时，仅靠让出事件循环为什么仍不够？何时应使用 Worker？

### 验收标准

- 十万层链不会栈溢出。
- 顺序、depth、path 正确。
- 有取消、环、重复 ID、深度和节点预算测试。
- 用可计数的假 <code>yieldControl</code> 验证让出次数，而不是依赖真实计时。
- 明确写出时间、显式栈、输出路径复制的空间复杂度。
