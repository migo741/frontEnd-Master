# 练习：设计 `useLatestTask`

## 题 1（75 分钟）

实现一个框架无关任务核心，再用 Vue composable 包装：

```ts
useLatestTask<P, R>(runner: (params: P, signal: AbortSignal) => Promise<R>)
```

暴露只读 `state` 和 `run/cancel`。后发任务必须赢；旧任务不能改 data/error/loading；取消不算错误；组件卸载自动取消。写 5 个 Vitest 用例，至少一个使用可控 Promise 反转完成顺序。

## 题 2（30 分钟）

审查一个 `useWindowSize`：它在模块顶层创建 ref 和监听器，SSR 报错，多个组件也永不释放。给出“每调用方独立”和“全应用单例”两种修复，说明各自所有权。

