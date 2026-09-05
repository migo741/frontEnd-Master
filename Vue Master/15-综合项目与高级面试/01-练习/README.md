# 第 15 章练习：毕业项目与生产答辩

> 本章恰好两题。第一题交付一条可运行的生产切片；第二题用事故演练和答辩证明你真的理解它。不要扩成题海。

## 题 1：FlowOps 工单分配 Vertical Slice

### 目标

用 Vue 3.5 + strict TypeScript 实现“查询工单 → 打开详情 → 分配处理人 → 遇到并发冲突 → 添加幂等评论”这一条完整切片。可用 Nuxt 4 做 universal SSR，也可用 Vite SPA + mock/真实 BFF；若不用 SSR，必须提交有数据的选型 ADR，而不是忽略它。

### 固定业务契约

- tenant A/B 数据必须隔离；角色为 viewer/agent/manager；
- URL 表达 `tenantId/filter/page/ticketId` 中可分享部分；
- list API 支持分页、稳定排序、AbortSignal；
- assign 命令包含 `baseVersion` 与 `idempotencyKey`，409 返回 current ticket；
- comment 命令用 client id/idempotency key，响应丢失后重试不得重复；
- realtime event 包含 `eventId/ticketId/entityVersion`，可能重复、乱序或断档；
- 10,000 工单测试数据，不能一次创建 10,000 行 DOM；
- 富文本/用户输入、日志、payload 和 source map 必须有安全边界。

### 交付物

1. `requirements.md`：角色、场景、不变量、失败状态、非目标、权限矩阵。
2. `architecture.md`：模块依赖、状态所有权、请求/事件流、trust boundary、SSR/CSR 决策。
3. schema + domain + repository port + HTTP/BFF adapter；不得让 `any` 穿过边界。
4. 可访问 UI：筛选、列表、详情、assignee combobox、评论 form、loading/empty/error/conflict/offline。
5. 竞态/资源处理：abort + generation、mutation single-flight/queue 策略、realtime dedupe/gap/reconnect、cleanup。
6. 测试：纯逻辑、component、integration、browser E2E、权限/安全；若 SSR，还要并发隔离/hydration/status/cache。
7. 性能证据：预算、固定 fixture、before/after trace、Vue 更新证据、bundle；不得只贴 Lighthouse 总分。
8. 发布证据：CI gate、immutable artifact、feature flag/canary、release dashboard、rollback/runbook。
9. 至少两份 ADR：状态/数据策略与 SSR/微前端/虚拟化中一个有争议决策；包含 rejected options。
10. README：一键运行、版本、demo 数据、测试命令、局限、已知风险与证据链接。

### 通过标准

- viewer 篡改前端状态仍无法分配；跨 tenant id 返回安全错误；
- A 慢 B 快时只显示 B；409 不静默覆盖；重复评论只有一条；
- event 重复不重复应用，version gap 会 refetch；
- 键盘能完成核心任务，焦点/错误提示可理解；
- 10,000 行下 DOM/INP 进入所定预算；路由反复进入退出无资源增长；
- canary 可关闭，旧客户端/API 兼容，回滚演练实际跑过。

### 时间盒

建议 30–45 小时：规格/架构 5h，domain/adapters 7h，UI/交互 12h，测试 8h，性能/安全/SSR 6h，发布/文档/答辩 4h。若时间不足，减少视觉和次要功能，不删除冲突、权限、失败和证据。

### 发散追问

把用户规模、团队和数据量都缩小十倍。你会删除哪些基础设施，保留哪些不变量？写一页“最小可负责版本”。

## 题 2：发布事故演练 + 45 分钟高级答辩

### 事故注入

在题 1 项目的预发/故障分支同时注入：

1. Nuxt 模块顶层 `ref` 保存 current tenant，且 dashboard HTML 被 CDN public cache；
2. 筛选列表把每行写成 `:ticket="{...ticket}"`，同步导入 700KB 图表；
3. websocket 和 `ResizeObserver` 在 KeepAlive deactivate 后不清理；
4. assign 成功后客户端超时重试，而服务端暂时忽略 idempotency key；
5. 新版 event schema 新增 breaking 字段，但旧 tab 仍在线；
6. release 后移动 LCP p75 从 2.4s 到 4.0s，跨租户泄漏出现 1 起。

### 交付物 A：事故处理

1. 前 15 分钟 triage/containment 清单：安全优先级、谁做什么、保留哪些证据。
2. 分钟级 timeline、用户影响、数据修复/通知升级条件。
3. root cause tree：trigger、latent conditions、blast-radius amplifiers、detection gaps。
4. 最小恢复方案与长期 corrective actions；每项有 owner、期限、验证，不写“提醒小心”。
5. 回滚/关闭 flag 后的验证矩阵；包括 CDN purge、进程状态、旧 tab、重复命令和监控。
6. postmortem + 三条能在 CI/平台执行的新 guardrail。

### 交付物 B：答辩

准备 15 分钟项目讲解与 30 分钟追问。必须能现场回答：

- 为什么状态没有全进 Pinia？
- 为什么 abort 后仍需要 generation？
- 409 conflict 与 optimistic UI 如何共存？
- SSR request isolation 如何测试？
- 为什么 route guard 不是授权？
- 虚拟化、分页、`v-memo` 如何按证据排序？
- 哪些测试不能由 unit mock 证明？
- 为什么不直接拆微前端/上 Vue 3.6 RC Vapor？
- release 如何兼容旧 tab，怎样回滚？
- 你方案最差的三个取舍是什么，什么指标会使你改选？

### 约束

- 跨租户泄漏按最高优先级安全事件处理，不能等“先查清再止血”；
- 不允许通过清空数据库掩盖重复命令；
- 不能同时盲改六处后宣称根因已找到；
- 复盘不得归因于“某开发粗心”；
- 答辩中数字必须说明样本、环境、分位数和前后版本。

### 发散追问

如果当时只有一名值班开发者、监控缺少 tenant/release 维度，你如何缩小动作并安全升级响应？
