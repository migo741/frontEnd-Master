# 第 06 章练习

## 练习一：可分享的商品检索页

URL 规范：

```text
/products?q=keyboard&category=office&sort=price-asc&page=2
```

要求：

- search params 是 q/category/sort/page 的唯一真相；无重复 `useState`。
- parser 将恶意/未知输入收敛为类型安全默认值；serializer 输出规范顺序并删除默认值。
- loader 接收 `request.signal`；代码和数据按路由并行加载。
- 输入搜索使用“草稿 + 提交/短 debounce 更新 URL”，不能每个按键都污染 history；分页使用可后退的 push，输入联想可 replace。
- 展示 pending、空、404/5xx；快速切换筛选不会出现旧结果。
- 测试刷新、复制 URL、前进后退和非法 page（负数、超大、非数字）。

额外：设计预取策略，说明为何不对所有商品链接立即预取。

## 练习二：权限、回跳与故障域（高难）

路由树：

```text
/
├── /login
└── /org/:orgId
    ├── /dashboard
    ├── /billing       (owner only)
    └── /reports/:id
```

任务：

- 根/组织/报表分别设计 loader 和 error boundary；组织壳失败不应错误展示成 report 404。
- 未登录跳 `/login?next=...`；实现 `safeReturnTo` 防 open redirect。
- 登录后会话已过期、组织不存在、无 billing 权限、报表服务 500 分别给不同处理。
- mutation 后只重验证受影响数据，不能粗暴刷新全应用。
- 设计发布后动态 chunk 404 的一次性恢复策略和可观测事件。
- 用内存路由测试关键分支，不依赖真实浏览器服务器。

交付一页 ADR：为什么客户端权限检查不是安全边界？

