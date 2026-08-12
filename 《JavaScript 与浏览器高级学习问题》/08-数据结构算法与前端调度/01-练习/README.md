# 第 08 章练习

## 练习一：把订单投影从嵌套扫描改成索引

实现 `joinOrders(orders, users)`。现有代码对每个订单调用一次 `users.find`，10 万订单、2 万用户时明显阻塞。

要求：

- 输出保持订单原顺序，不修改任一输入或实体对象；
- 先构建 `userId -> user` 索引，总时间目标 O(users + orders)；
- 重复 user id 立即失败，错误包含 id；
- 找不到 owner 的订单保留，但输出 `owner: null` 并汇总 missing 数；
- 无效 id、空数组和同一用户被大量订单引用都有测试；
- 保留慢速实现作为测试 oracle，对随机小数据比较两版结果；
- 在固定数据、同一设备上各运行至少 20 次，报告 p50/p95 与常驻内存变化。

验收：不能只给 `console.time` 截图；解释什么数据规模下仍会选择简单的 `find` 版本。

## 练习二：动态行高虚拟列表索引（高难）

实现 `HeightIndex`：

```js
const index = new HeightIndex([20, 30, 25])
index.update(1, 40)
index.offsetOf(2) // 前两行总高度 60
index.visibleRange({scrollTop: 18, viewportHeight: 35, overscan: 10})
```

要求：

- 10 万行初始化可接受；`update`、`offsetOf` 和按像素定位行均为 O(log n)；
- 行高必须为有限正数，越界更新明确报错；
- `visibleRange` 返回半开区间 `{start, end}`，正确处理边界、空列表和滚动超过总高；
- overscan 以像素而非固定行数计算；
- 随机执行 1 万次 update/query，与 O(n) 数组 oracle 对比；
- 容器 ResizeObserver 连续触发时，只提交最新测量并避免反馈循环；
- 说明估算高度变成实测高度后，如何保持锚点行不突然跳动。

不要求完成 UI；重点是数据结构、不变量和验证证据。

## 复盘交付

用一张表对比：全量前缀数组、Fenwick Tree、固定行高公式在查询、更新、内存与实现复杂度上的取舍。
