# 第 15 章参考答案

## 练习一

典型保持链不是“DOM 没删”，而是：

```text
Window -> resize listener -> closure -> viewModel -> 50k rows
Module Map -> drawer id -> detached element -> subtree/listeners
ResizeObserver -> callback -> drawer element
Timer queue -> interval callback -> viewModel
```

建议把所有资源归到单个会话并返回幂等 disposer：

```js
export function mountDrawer(host, data) {
  const controller = new AbortController()
  const element = renderDrawer(data)
  host.append(element)

  const onResize = () => layout(element)
  window.addEventListener('resize', onResize, {signal: controller.signal})

  const observer = new ResizeObserver(() => layout(element))
  observer.observe(element)

  const timer = setInterval(() => refreshClock(element), 1000)
  drawerRegistry.set(element, {openedAt: Date.now()})

  let disposed = false
  return () => {
    if (disposed) return
    disposed = true
    controller.abort()
    observer.disconnect()
    clearInterval(timer)
    drawerRegistry.delete(element)
    element.remove()
  }
}
```

`AbortSignal` 方便成组清理支持 signal 的监听器，但不能替代 observer/timer/Map 的显式释放。把 disposer 设计为幂等，可承受路由退出、错误边界和用户关闭同时触发。

三快照报告应说明：A/B/C 发生在强制回稳态后；比较对象数量与 retained size；找到业务对象的 retaining path，而不是只引用总 heap。修复后允许 GC 噪声波动，但 B→C 不应随操作次数线性增加。

自动化可以暴露调试计数器，或在测试环境注入资源工厂：

```js
for (let i = 0; i < 100; i++) {
  const dispose = mountDrawer(host, fixture)
  dispose()
}
expect(host.childElementCount).toBe(0)
expect(drawerRegistry.size).toBe(0)
expect(resourceTracker.active).toEqual({timers: 0, observers: 0, listeners: 0})
```

浏览器 heap 的最终回收不可用同步断言保证，所以自动测试守资源所有权，快照实验守真实回收。

## 练习二

一个合理的定位顺序：

1. 输入前有实时推送的 120ms 数据归并任务，造成输入延迟；
2. 输入处理器每键对 2 万行执行多次线性扫描，处理 70ms；
3. commit 后 2 万 DOM 行触发布局/绘制，呈现 180ms；
4. 图表脚本还占用首屏带宽并推迟 LCP。

对应的最小修复集可能是：

- 按 id 建索引，筛选预归一化字符串，避免重复扫描/转换；
- 推送按帧或固定窗口合并，后台计算移到 Worker，并丢弃过期代次；
- 使用可访问的虚拟列表限制 DOM，而不是只 memo 行组件；
- 输入值保持紧急更新，结果提交可用 Transition；
- 图表按路由/视口懒加载，给容器预留尺寸防 CLS。

报告表例：

| 指标 | 基线 p50/p75 | 修改后 p50/p75 | 条件 | 结论 |
|---|---:|---:|---|---|
| INP 场景 | 410/530ms | 135/182ms | 4× CPU、Fast 4G | 达标 |
| 交互最大长任务 | 210ms | 42ms | 同上 | 已切片/移出 |
| 活跃 DOM 节点 | 24,800 | 620 | 20k 行 | 受控 |
| LCP | 3.1s | 2.3s | 冷缓存 | 达标 |
| CLS | 0.18 | 0.04 | 冷缓存 | 达标 |

性能预算可在固定环境跑关键页面 trace，限制路由初始 JS、长任务数量和关键场景时间；真实发布再以 RUM p75 做守门或回滚信号。不要让实验室单次波动直接阻断所有发布，应设置重复、容差和趋势规则。

复写任务：关闭答案，用“用户现象 → 时间线 → 最大成本 → 最小改变 → 证据”五行重写自己的优化结论；任何没有数据的优化从提交中删除。

