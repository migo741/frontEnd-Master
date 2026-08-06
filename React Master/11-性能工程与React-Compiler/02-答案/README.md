# 第 11 章参考答案

## 练习一：合格证据链

可能结论：

1. 网络瀑布是首屏最大瓶颈：route match 时并行启动三个请求/聚合 API，往往比 memo 收益大。
2. 巨型 Context 让无关消费者 render：按变化频率拆 provider，actions 稳定，或 selector store；状态下沉。
3. 行内重复日期/权限计算：把不随 render 变化的解析移数据边界，按 user/permission 预建 Map；可见列表虚拟化。只有剩余昂贵纯计算才 memo。

Compiler 实验需确保不是开发 build，修复 lint purity 后选择单 feature，保存 before/after profile。编译器可能让手写 memo 边际收益下降，但加载瀑布和 DOM 数量不会改变。

CI 可检查 route chunk gzip 上限、Lighthouse CI 的性能预算、关键交互 Playwright trace/自定义 long task，或 bundle diff。实验室指标有噪声，应多次运行、设合理容差，不让 CI 随机红。

## 练习二：参考架构

```text
WebSocket bytes
  -> Worker 解码/校验/序列号
  -> 16~100ms 微批 delta（按 entityId 合并，只保留批内最后值）
  -> normalized external store
  -> 可见 id selector / row selector
  -> virtualized viewport
```

每秒 2,000 update 若逐条通知 React 会造成调度开销。Worker 解析，主线程按帧/时间片批量提交；不可见实体更新只改 store，不让可见 selector 变。排序若依据实时价格，不能每 tick 全量 O(n log n)；可降低排序刷新频率、使用增量索引或把严格排序交服务端，并在 UI 标注更新时间。

虚拟列表只渲染约 30–100 行；每行订阅自己的 `id -> selected fields`，selection 保存 Set<id>，不要复制行对象。固定列可共享垂直虚拟模型，避免两个列表滚动漂移。

序列号检测缺口：暂停应用增量/标记 stale，请求 snapshot + lastSequence，再原子替换并继续；队列超预算时丢弃中间可合并价格 delta，不能丢订单状态等不可合并事件。降级开关：降低刷新率、暂停闪烁动画、关闭实时排序、减少 overscan、切分页。

监控：delta lag p95、主线程 long task、可见行 commit p95、丢/合并事件数、重同步率、内存/DOM 节点。可访问性可提供分页/静态表格模式，让屏幕阅读器访问完整语义；键盘焦点采用 active-descendant 或 focus sentinel，不能在行卸载时丢失无解释。

