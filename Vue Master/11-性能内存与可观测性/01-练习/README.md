# 第 11 章练习：用证据做性能工程

> 本章恰好两题。不要先写“懒加载、缓存、CDN”；先写证据、因果链和验收。

## 题 1：五天内救回 OpsBoard（性能预算 + 更新路径）

### 背景

`/operations` 是 Vue 3.5 + Vite 的 SPA，首屏包含 20,000 行工单和一个默认折叠的图表抽屉。灰度数据：

- 移动端 LCP p75 = 4.1s；
- INP p75 = 380ms，筛选输入最差可到 850ms；
- CLS p75 = 0.04；
- 初始 JS = 1.3MB gzip；
- 一次筛选后 Vue Devtools 显示约 8,000 个 `TicketRow` 更新；
- 当前实现每次 render 都执行 `:ticket="{ ...ticket }"`，并把 `selectedId` 传给每行；
- 折叠图表依赖约 700KB gzip，首屏同步导入。

你只有 5 个工作日，不能改后端接口，也不能牺牲键盘操作和所有工单的可访问能力。

### 交付物

1. 写出从 RUM → Network/Performance → Vue Devtools 的诊断顺序；每一步必须说明它能证实/排除什么。
2. 画出 LCP 和筛选 INP 的因果链。
3. 最多选择三项生产改动，并解释为什么比其余候选优先。
4. 为列表写出关键 Vue/TypeScript 代码或伪代码，必须体现 props stability 与虚拟窗口/分页之间的选择。
5. 定义 PR、预发、灰度三层回归预算；包括失败与回滚条件。
6. 写出至少四个可能反证你方案的结果，以及遇到反证后下一步查什么。

### 验收限制

- 不接受只报 Lighthouse 分数；
- 不接受把 20,000 行截成前 50 行；
- 不接受无测量地“全上 `v-memo`”；
- 需要说明动态高度、焦点、读屏或搜索功能会怎样影响虚拟化选型；
- 所有阈值要标明“通用参考”还是“本产品预算”。

### 发散追问

若虚拟列表库无法满足读屏器完整表格语义，你会选择服务端分页、非虚拟化降级，还是双视图？写 ADR 的决策因素，不要求唯一答案。

## 题 2：地图页每次来回多 20MB（内存 + 可观测性）

### 背景

`MapPage.vue` 被 `<KeepAlive>` 缓存。它创建地图 SDK、`ResizeObserver`、`window.resize` listener、5 秒轮询和 WebSocket；离开页面只调用 `socket.close()`。测试人员重复“列表 → 地图 → 列表”十次后发现 heap 增长约 200MB，地图 marker 点击还会被重复处理。

### 交付物

1. 设计一个固定数据、可重复的最小复现脚本；区分 deactivate 与 unmount。
2. 写出 baseline、循环后、修复后三组 heap/DOM/listener 证据的采集步骤。
3. 列出至少六类可能 retained path，并说明各自真正的 owner 可能是谁。
4. 用 strict TypeScript 写一个 `useMapSession` 的资源生命周期骨架，必须处理：
   - mount/activate 启动且幂等；
   - deactivate/unmount 停止且幂等；
   - AbortController 或等价请求取消；
   - SDK destroy、observer、listener、timer、socket 全部成对清理；
   - 避免旧异步响应复活已停止 session。
5. 定义“不是泄漏”的反证，以及修复验收平台值。
6. 设计一个开发期资源计数器或自动化生命周期测试，防止同类回归。

### 验收限制

- 不能以“变量设为 null”作为主要修复；
- 不能只看任务管理器总内存；
- 必须沿 retained path 指到 owner；
- 必须验证页面重新激活后功能仍正常，而不只是内存下降。

### 发散追问

地图产品要求后台仍接收告警，但不可继续渲染 marker。如何把“数据连接生命周期”和“视图资源生命周期”拆成两个所有者？
