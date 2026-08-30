# 第 06 章答案

答案的价值在于复盘建模和边界，不是背代码。建议先把自己的实现与“契约、不变量、失败行为”逐项对照。

## 练习 1 答案：安全求值规则表达式树

### 1. 建模

递归版本看起来简单，但它隐式保存了三类状态：

- 当前节点；
- 对 and/or 来说，下一个要访问的孩子下标和已经累计的结果；
- 子调用返回后，父节点应该继续执行的位置。

显式栈应保存同样的信息。为了实现短路，不能简单地先把所有孩子压栈；必须让父帧一次推进一个孩子。

我们使用两类帧：

- <code>VisitFrame</code>：第一次进入一个节点；
- <code>CombineFrame</code>：一个复合节点等待孩子结果，并保存下一个孩子下标。

值栈保存已经完成的子表达式结果。<code>active</code> 保存已进入但尚未完成的对象身份。

### 2. 朴素方案与瓶颈

朴素递归在合法浅树上是正确的，但深度由外部输入控制时可能栈溢出。另一个朴素迭代方案是把所有节点先做后序排列再统一计算，但它无法自然短路，并会访问本来无需访问的危险分支。

### 3. 参考实现

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

interface VisitFrame {
  readonly type: "visit";
  readonly node: Rule;
  readonly depth: number;
}

interface CombineFrame {
  readonly type: "combine";
  readonly node: Exclude<Rule, { readonly kind: "literal" }>;
  readonly depth: number;
  nextChildIndex: number;
  awaitingChild: boolean;
  accumulated: boolean;
}

type Frame = VisitFrame | CombineFrame;

function assertPositiveInteger(value: number, name: string): void {
  if (!Number.isSafeInteger(value) || value <= 0) {
    throw new RangeError(name + " must be a positive safe integer");
  }
}

function unreachable(value: never): never {
  throw new TypeError(
    "Unsupported rule kind: " + String((value as { kind?: unknown }).kind),
  );
}

export function evaluateRule(
  root: Rule,
  options: EvaluateOptions,
): boolean {
  assertPositiveInteger(options.maxDepth, "maxDepth");
  assertPositiveInteger(options.maxNodes, "maxNodes");

  const frames: Frame[] = [{ type: "visit", node: root, depth: 0 }];
  const values: boolean[] = [];
  const active = new Set<object>();
  let visitedNodes = 0;

  while (frames.length > 0) {
    const frame = frames[frames.length - 1];

    if (frame.type === "visit") {
      frames.pop();

      if (frame.depth > options.maxDepth) {
        throw new RangeError("Rule exceeds maxDepth");
      }
      visitedNodes += 1;
      if (visitedNodes > options.maxNodes) {
        throw new RangeError("Rule exceeds maxNodes");
      }
      if (active.has(frame.node)) {
        throw new TypeError("Rule contains an object-reference cycle");
      }

      switch (frame.node.kind) {
        case "literal":
          values.push(frame.node.value);
          break;

        case "not":
          active.add(frame.node);
          frames.push({
            type: "combine",
            node: frame.node,
            depth: frame.depth,
            nextChildIndex: 0,
            awaitingChild: false,
            accumulated: false,
          });
          break;

        case "and":
          if (frame.node.children.length === 0) {
            values.push(true);
            break;
          }
          active.add(frame.node);
          frames.push({
            type: "combine",
            node: frame.node,
            depth: frame.depth,
            nextChildIndex: 0,
            awaitingChild: false,
            accumulated: true,
          });
          break;

        case "or":
          if (frame.node.children.length === 0) {
            values.push(false);
            break;
          }
          active.add(frame.node);
          frames.push({
            type: "combine",
            node: frame.node,
            depth: frame.depth,
            nextChildIndex: 0,
            awaitingChild: false,
            accumulated: false,
          });
          break;

        default:
          unreachable(frame.node);
      }
      continue;
    }

    if (frame.awaitingChild) {
      const childValue = values.pop();
      if (childValue === undefined) {
        throw new Error("Internal evaluator invariant was broken");
      }
      frame.awaitingChild = false;

      if (frame.node.kind === "not") {
        active.delete(frame.node);
        frames.pop();
        values.push(!childValue);
        continue;
      }

      if (frame.node.kind === "and") {
        frame.accumulated = frame.accumulated && childValue;
        if (!frame.accumulated) {
          active.delete(frame.node);
          frames.pop();
          values.push(false);
          continue;
        }
      } else if (frame.node.kind === "or") {
        frame.accumulated = frame.accumulated || childValue;
        if (frame.accumulated) {
          active.delete(frame.node);
          frames.pop();
          values.push(true);
          continue;
        }
      }
    }

    const children =
      frame.node.kind === "not"
        ? ([frame.node.child] as const)
        : frame.node.children;

    if (frame.nextChildIndex >= children.length) {
      active.delete(frame.node);
      frames.pop();
      values.push(frame.accumulated);
      continue;
    }

    const child = children[frame.nextChildIndex];
    frame.nextChildIndex += 1;
    frame.awaitingChild = true;
    frames.push({
      type: "visit",
      node: child,
      depth: frame.depth + 1,
    });
  }

  if (values.length !== 1) {
    throw new Error("Internal evaluator produced an invalid value stack");
  }
  return values[0];
}
~~~

### 4. 正确性

核心不变量：

1. 每个 combine 帧对应一个已加入 <code>active</code>、尚未完成的复合节点。
2. <code>awaitingChild=true</code> 时，它刚压入的孩子最终会在值栈顶留下且仅留下一个结果。
3. 一个复合节点累计值只包含下标小于 <code>nextChildIndex</code> 的已完成孩子。
4. and 的累计值初始为 true，or 初始为 false；短路发生时，未访问孩子不可能改变最终结果。

literal 直接产生正确值；not 对唯一孩子取反；and/or 按布尔恒等元累积。每个有限且合法的节点最终要么产生一个值，要么明确失败，所以根节点最终留下唯一正确值。

### 5. 复杂度

设实际因短路而访问的节点数为 <code>v</code>，最大访问深度为 <code>h</code>：

- 时间：<code>O(v)</code>；
- 帧栈：<code>O(h)</code>；
- active：<code>O(h)</code>；
- 值栈：本实现最多与深度同阶，为 <code>O(h)</code>。

最坏情况下 <code>v=n</code>。预算检查使资源消耗在外部输入下仍有明确上界。

### 6. 测试示例

~~~ts
import { describe, expect, it } from "vitest";

const limits = { maxDepth: 100_000, maxNodes: 100_000 };

describe("evaluateRule", () => {
  it("supports identities and short circuit", () => {
    expect(evaluateRule({ kind: "and", children: [] }, limits)).toBe(true);
    expect(evaluateRule({ kind: "or", children: [] }, limits)).toBe(false);

    const skipped: Rule = {
      kind: "not",
      child: { kind: "literal", value: false },
    };
    expect(
      evaluateRule(
        {
          kind: "or",
          children: [{ kind: "literal", value: true }, skipped],
        },
        { maxDepth: 10, maxNodes: 2 },
      ),
    ).toBe(true);
  });

  it("handles a very deep chain without call-stack recursion", () => {
    let rule: Rule = { kind: "literal", value: true };
    for (let index = 0; index < 50_000; index += 1) {
      rule = { kind: "not", child: rule };
    }
    expect(evaluateRule(rule, limits)).toBe(true);
  });

  it("rejects a reference cycle", () => {
    const cyclic = { kind: "not" } as { kind: "not"; child: Rule };
    cyclic.child = cyclic;
    expect(() => evaluateRule(cyclic, limits)).toThrow(/cycle/);
  });
});
~~~

### 7. 失败边界与生产替代

这仍不是完整的权限引擎。生产系统还需要运行时 schema 校验、规则版本、可观测性、审计、变量读取授权、确定的错误码和超时策略。复杂规则最好编译成受限中间表示并缓存，而不是每次从任意对象求值。若规则需要跨服务取数，短路、超时和并发限制必须在更高层设计。

## 练习 2 答案：可取消、分批让出执行权的层级数据导入器

### 1. 建模

前序遍历的顺序是“当前节点，然后依次遍历孩子”。显式栈采用 enter/exit 帧：

- enter 帧产出当前记录，把对象加入当前路径；
- 随后压入 exit 帧，并逆序压入孩子；
- exit 帧从当前路径删除对象。

不过简单地一次压入所有孩子会破坏 active 的含义：兄弟 enter 帧都在栈中，但并未真正进入。正确做法是使用保存 <code>nextChildIndex</code> 的游标帧，一次推进一个孩子，这也避免一个超宽节点瞬间压入百万帧。

### 2. 朴素方案与瓶颈

- 递归 DFS：深链会栈溢出。
- 一次性同步 while：不会栈溢出，但仍阻塞事件循环。
- 每个节点都 <code>await yieldControl()</code>：响应性好但调度开销过大。
- 用一个共享可变 path 返回：消费者保存记录后，后续 pop 会篡改历史结果。

本实现按批让出，并在产出时复制 path，以换取稳定快照。

### 3. 参考实现

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

interface CursorFrame {
  readonly node: ImportNode;
  readonly depth: number;
  nextChildIndex: number;
  entered: boolean;
}

function assertBudget(value: number, name: string): void {
  if (!Number.isSafeInteger(value) || value <= 0) {
    throw new RangeError(name + " must be a positive safe integer");
  }
}

function abortError(): Error {
  return new DOMException("Traversal was aborted", "AbortError");
}

export async function* walkInBatches(
  roots: readonly ImportNode[],
  options: WalkOptions,
): AsyncGenerator<FlatRecord, void, void> {
  assertBudget(options.batchSize, "batchSize");
  assertBudget(options.maxDepth, "maxDepth");
  assertBudget(options.maxNodes, "maxNodes");

  const active = new Set<object>();
  const ids = new Set<string>();
  const path: string[] = [];
  let visited = 0;
  let sinceYield = 0;

  const virtualRoot: ImportNode = { id: "", children: roots };
  const stack: CursorFrame[] = [{
    node: virtualRoot,
    depth: -1,
    nextChildIndex: 0,
    entered: true,
  }];

  while (stack.length > 0) {
    if (options.signal?.aborted === true) {
      throw abortError();
    }

    const frame = stack[stack.length - 1];

    if (frame.node !== virtualRoot && !frame.entered) {
      if (frame.depth > options.maxDepth) {
        throw new RangeError("Tree exceeds maxDepth");
      }
      if (active.has(frame.node)) {
        throw new TypeError("Tree contains an object-reference cycle");
      }
      if (ids.has(frame.node.id)) {
        throw new TypeError("Duplicate business id: " + frame.node.id);
      }

      visited += 1;
      if (visited > options.maxNodes) {
        throw new RangeError("Tree exceeds maxNodes");
      }

      frame.entered = true;
      active.add(frame.node);
      ids.add(frame.node.id);
      path.push(frame.node.id);

      yield {
        id: frame.node.id,
        depth: frame.depth,
        path: path.slice(),
      };

      sinceYield += 1;
      if (sinceYield >= options.batchSize) {
        sinceYield = 0;
        if (options.signal?.aborted === true) throw abortError();
        await options.yieldControl();
        if (options.signal?.aborted === true) throw abortError();
      }
      continue;
    }

    if (frame.nextChildIndex < frame.node.children.length) {
      const child = frame.node.children[frame.nextChildIndex];
      frame.nextChildIndex += 1;
      if (active.has(child)) {
        throw new TypeError("Tree contains an object-reference cycle");
      }
      stack.push({
        node: child,
        depth: frame.depth + 1,
        nextChildIndex: 0,
        entered: false,
      });
      continue;
    }

    stack.pop();
    if (frame.node !== virtualRoot) {
      active.delete(frame.node);
      path.pop();
    }
  }
}
~~~

### 4. 正确性

循环顶部维持：

1. 除虚拟根外，栈中所有 <code>entered=true</code> 的帧按顺序构成当前根到当前节点的路径。
2. <code>path</code> 与上述帧的 ID 一一对应，且 <code>active</code> 恰好包含这些对象。
3. 每个帧下标之前的孩子已经完整遍历，之后的孩子尚未进入。
4. 每个已产出的业务 ID 已加入 ids，因此不会重复产出。

进入节点时先产出再推进孩子，得到前序；每个父帧按 children 下标递增推进，保持同级顺序。完成节点后同时弹帧、path 和 active，故路径不变量保持。

### 5. 复杂度

设节点数为 <code>n</code>，最大深度 <code>h</code>：

- 遍历控制本身为 <code>O(n)</code>；
- 显式栈、active、当前 path 为 <code>O(h)</code>；
- 全局 ID 集合为 <code>O(n)</code>；
- 由于每条结果复制长度为当前深度的 path，总复制量是所有节点深度之和，最坏退化链为 <code>O(n²)</code>。

最后一点正是开放设计问题的关键：输出本身要求每条完整路径时，平方级总字符/引用数量可能是不可避免的。可以改为产出 <code>parentId</code>、持久化路径编码、共享不可变链节点，或提供只在回调期间有效的路径视图。

### 6. 测试示例

~~~ts
import { expect, it, vi } from "vitest";

it("walks in stable preorder and yields by batch", async () => {
  const yieldControl = vi.fn(async () => undefined);
  const roots: ImportNode[] = [{
    id: "a",
    children: [
      { id: "b", children: [] },
      { id: "c", children: [] },
    ],
  }];

  const actual: FlatRecord[] = [];
  for await (const record of walkInBatches(roots, {
    batchSize: 2,
    maxDepth: 10,
    maxNodes: 10,
    yieldControl,
  })) {
    actual.push(record);
  }

  expect(actual.map((item) => item.id)).toEqual(["a", "b", "c"]);
  expect(actual[1].path).toEqual(["a", "b"]);
  expect(yieldControl).toHaveBeenCalledTimes(1);
});

it("stops when the consumer stops", async () => {
  let yields = 0;
  const iterator = walkInBatches(
    [{ id: "a", children: [{ id: "b", children: [] }] }],
    {
      batchSize: 1,
      maxDepth: 10,
      maxNodes: 10,
      yieldControl: async () => { yields += 1; },
    },
  );

  await iterator.next();
  await iterator.return();
  expect(yields).toBe(0);
});
~~~

### 7. 失败边界与生产替代

生成器只负责遍历，不等同于可靠导入。数据库写入应使用明确批次 ID 和幂等键；事务批量不能无限大；失败后要记录最后已提交检查点，而不是依赖内存生成器状态。多个父节点共享一个对象是否允许必须成为 schema 契约。若每节点计算很重，应把 CPU 工作移到 Worker；若数据本身来自流，应避免先构造整棵内存树，改为流式解析或服务端分页。

