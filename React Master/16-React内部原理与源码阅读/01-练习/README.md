# 第 16 章练习

## 练习一：手算协调与 Hook 队列

旧树：

```tsx
<>
  <Row key="a" label="A" />
  <Row key="b" label="B" />
  <Row key="c" label="C" />
</>
```

新树：

```tsx
<>
  <Row key="c" label="C2" />
  <SpecialRow key="b" label="B2" />
  <Row key="d" label="D" />
</>
```

任务：

- 对 a/b/c/d 判断复用、移动、删除、新建、state 保留；解释 b 同 key 不同 type。
- 画 current/WIP 与 commit 变化，不要求私有字段精确。
- 对 `setN(n+1); startTransition(()=>setN(x=>x+10)); setN(x=>x+2)` 画概念队列，讨论不同优先级 render/重放如何保持最终一致。
- 写一个测试验证你对 state 保留的预测。

## 练习二：源码证据报告（高难）

从以下选一题：

1. `useSyncExternalStore` 如何避免 render/commit 间快照变化导致撕裂？
2. React 19.2 `useEffectEvent` 的 lint/运行时限制如何落地？
3. `useState` 函数式更新在队列中如何处理被跳过 lane？
4. React Compiler 生成代码如何缓存一个组件表达式？

要求：

- 固定 React/插件 tag 或 commit hash；记录仓库链接与日期。
- 先写公开行为的最小测试，再找源码/官方测试。
- 输出不超过 5 页：问题、公开契约、调用路径、关键数据结构、实验、结论、版本依赖/未知。
- 源码引用每段不超过必要范围，用链接+行号，不复制大段。
- 至少推翻一个你最初的假设。

## 验收

若报告只列函数名而没有行为证据，不通过；若把私有字段当公共 API，也不通过。

