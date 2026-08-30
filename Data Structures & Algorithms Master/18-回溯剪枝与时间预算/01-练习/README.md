# 练习：在组合爆炸中保持正确与可控

## 题 1：N 皇后求解与计数（经典机制）

```ts
interface QueensResult {
  readonly firstSolution: readonly number[] | null; // index=row, value=col
  readonly solutionCount: bigint;
  readonly visitedNodes: number;
}

declare function solveNQueens(n: number): QueensResult;
```

要求：支持 `0 <= n <= 14`；按行搜索，列从小到大，因此首解确定；使用列与两类对角线剪枝；返回一个首解和全部解数量；输入 0 定义为一个空棋盘解。写出搜索不变量和终止条件，解释为何计数用 BigInt。

测试已知小值：`n=0,1,2,3,4` 的解数分别为 `1,1,0,0,2`；对每个返回首解使用独立 validator；故意删掉一次撤销操作，给出最小失败现象。

## 题 2：功能配置约束求解器（生产/开放）

```ts
interface ConfigProblem {
  readonly features: readonly string[];
  readonly required: readonly string[];
  readonly forbidden: readonly string[];
  readonly implies: readonly (readonly [string, string])[];
  readonly conflicts: readonly (readonly [string, string])[];
  readonly exactlyOne: readonly (readonly string[])[];
}

type ConfigResult =
  | { readonly status: "solved"; readonly selected: readonly string[]; readonly visitedNodes: number }
  | { readonly status: "unsatisfiable"; readonly visitedNodes: number; readonly reason: string }
  | { readonly status: "budgetExceeded" | "aborted"; readonly visitedNodes: number };

declare function solveFeatureConfig(
  problem: ConfigProblem,
  options: { readonly maxNodes: number; readonly signal?: AbortSignal },
): ConfigResult;
```

要求：验证重复/未知 feature 和空 exactlyOne；做 implies、conflicts 与 exactlyOne 传播；用“约束度最高的未知变量”近似 MRV；值顺序先 true 后 false；同一输入结果确定。预算耗尽与已证明无解必须区分。每个 solved 结果交给独立 `validateCompleteConfig` 再验证。

交付：实现、状态不变量、至少 12 个定向测试、固定 seed 小规模与暴力枚举差分、访问节点统计。

发散：

1. 怎样返回较小的冲突解释，而不是一句 `unsatisfiable`？
2. 加入“尽量满足 desired features”后如何做 branch-and-bound？
3. 规则由租户提交时，怎样防止 CPU/内存拒绝服务？
4. 何时应迁移到 SAT/CP-SAT，而不是继续加 if？

