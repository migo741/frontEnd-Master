# 第 17 章练习

## 练习一：可靠的 Canvas 波形组件

一个 React 波形组件需要：Canvas 绘制、ResizeObserver、自适应 DPR、pointer 拖动、键盘移动光标、`onSelect(sampleId)` 回调。现有实现把 listener 放在空依赖 Effect 中，回调读取初次 props；每次 render 创建 Worker；ResizeObserver 直接同步 setState；卸载后偶发消息更新。

任务：

1. 画出 React、Canvas、Worker、observer、pointer listener 各自的所有权和生命周期；
2. render 保持纯，Worker 不因普通 render 重建；setup/cleanup 在 Strict Mode 下对称；
3. 事件读取最新 `onSelect`，但不为每次回调变化重建昂贵资源；React 19.2 与 React 18 各给一种方案；
4. Worker 响应带 generation，旧数据结果不得覆盖；DPR/尺寸变化批量到下一帧绘制；
5. 提供键盘等价交互和可访问名称；
6. 用测试证明重复挂载/卸载无多余 listener/Worker，旧消息无效。

不要把所有数据都塞进 ref 来绕开 React；说明哪些是 UI state、哪些是外部资源句柄。

## 练习二：Worker 查询的 React 适配层（高难）

设计 `<WorkerQueryProvider>` 与 `useWorkerQuery(query)`，供多个组件共享一个 Worker 和缓存。

约束：

- Provider 拥有 Worker；最后一个消费者离开后按策略释放；
- 相同规范化 query 去重，缓存是不可变稳定 snapshot；
- query 改变时旧结果不能覆盖；外部 store 必须同步发布真实变化，若结果展示昂贵，用 `useDeferredValue` 或组件本地派生 state 延迟呈现，不能把外部 store mutation 伪装成非阻塞 Transition；
- 每条缓存记录显式 `idle/pending/success/error`，取消不是 error；
- `useSyncExternalStore` 的 subscribe/getSnapshot 契约正确，不产生无限 render/tearing；
- SSR 返回确定的 server snapshot，hydrate 后再启动 Worker；
- Worker 崩溃时所有相关记录进入可重试状态；缓存有容量和淘汰策略。

交付：store 核心、Hook 伪码或实现、状态图、并发/Strict Mode/SSR/缓存淘汰测试。说明为什么“在每个组件的 Effect 里 new Worker”不是只差一点性能。
