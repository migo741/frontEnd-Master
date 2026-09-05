# 第 14 章答案：边界、契约、迁移与前沿实验

## 题 1 参考答案：模块化单体优先，计费提取设闸门

### 1. 判断

不在三个月内直接拆四个 runtime microfrontend。当前跨域原子变更多、边界未执行、平台只有两人，运行时拆分会把源码耦合变成版本/网络/发布耦合。先用 60–90 天形成模块化单体、增量 pipeline 和 public contract；计费是唯一候选，但只有达到提取闸门后才独立运行时部署。

这不是否定微前端，而是让可逆且便宜的动作先产生证据。

### 2. 目标结构与规则

```text
src/
├─ app/                       # router/providers/composition root
├─ modules/
│  ├─ orders/
│  │  ├─ domain/
│  │  ├─ application/
│  │  ├─ infrastructure/
│  │  ├─ ui/
│  │  └─ public.ts
│  ├─ customers/{...}
│  ├─ billing/{...}
│  └─ support/{...}
└─ shared/
   ├─ kernel/
   ├─ platform/
   └─ ui/
```

规则：

- `domain` 只能依赖本域 domain 与极小 shared kernel；禁止 Vue/Pinia/fetch。
- `application` 可依赖 domain 和 port 类型，禁止 concrete infrastructure/ui。
- `infrastructure` 实现 port，可依赖 HTTP/schema；UI 通过注入使用 port。
- 跨域只能导入对方 `public.ts`，禁止 `modules/x/internal/path`。
- `shared` 禁止依赖任何 module；`app` 可组装但不写领域规则。
- DTO 在 infrastructure 校验转换，禁止 `any` 穿过 public boundary。

ESLint restricted-imports + dependency graph 工具 + 自定义 boundary test 在 CI 阻止违规。用 CODEOWNERS 标 public contract reviewer；构建图只跑受影响模块 unit/type/test，再保留夜间全仓组合测试。先 profile 70 分钟，区分安装、类型、测试和 bundle 的真实瓶颈。

### 3. 方案矩阵

| 维度 | 模块化单体 | Package 化 | 四个 MFE | 计费候选 MFE |
| --- | --- | --- | --- | --- |
| 跨域原子变更 | 强 | 强/中 | 弱 | 订单-计费需兼容协议 |
| 独立发布 | 中 | 中 | 强 | 计费强 |
| 当前团队边界匹配 | 中 | 中 | 差 | 较好 |
| 运行时故障面 | 低 | 低 | 高 | 中 |
| 平台投入 | 低/中 | 中 | 很高 | 可控但仍需增员/缩范围 |
| 首屏与重复依赖 | 易控 | 易控 | 风险高 | 局部预算 |
| route/a11y/样式一致性 | 易 | 易 | 难 | 中 |
| 回滚 | 单一 release | 包版本 | remote+shell 矩阵 | 有界矩阵 |
| 契约成熟度要求 | 可边做边学 | 中 | 高但当前缺失 | 先设闸门 |
| 三个月可达性 | 高 | 中 | 低 | 仅 spike/canary 可达 |

“维持现状”不满足依赖与 pipeline；package 化可作为计费 public API 的中间台阶。决定：先模块化单体，计费先 package contract，满足闸门后才 runtime 提取。不做：不拆其余三域、不引入跨应用任意 event bus、不以混用框架为目标。

### 4. ADR 摘要

```md
# ADR-014: 先模块化单体，并条件式提取 Billing
Status: Accepted

Context:
- 45 人；仅 Billing 稳定自治
- 跨域原子发布频繁
- 全仓测试 70m，但尚未拆解瓶颈
- 无 contract/remote rollback/统一 observability

Decision:
90 天内建立四个业务模块和强制 public boundary；Billing 先 package 化。
只有当连续 6 周 ≥70% Billing 发布不要求其他域同版本、contract tests 完整、
remote fallback/rollback 演练通过且性能预算达标，才进入 runtime canary。

Negative consequences:
- 暂时不能完全独立部署
- 需付双入口/adapter 与 boundary 修复成本
- 平台两人必须减少并行目标

Rejected:
- 四 MFE：边界/平台/耦合证据不支持
- 维持现状：无法控制依赖与 pipeline

Revisit:
- Billing 独立变更率、跨域发布率、pipeline、故障/回滚数据变化
- 订单与计费 API 已具向后兼容窗口
```

90 天里程碑：

- 0–30 天：量 CI、冻结新增 deep import、DTO schema、关键旅程基线；业务照常发布。
- 31–60 天：四域目录/public API、受影响测试、owners；将违规数降到 0 或有带期限豁免。
- 61–90 天：Billing package、版本化契约、shell/remote spike、timeout/fallback/rollback drill。

示例验收：受影响 PR p75 < 15 分钟；跨域 deep import 0；billing public contract 覆盖 100% 暴露项；组合关键旅程成功率不降；额外 initial JS 在预算内；remote 故障 2 秒内降级；任何身份泄漏为立即停止。

### 5. Billing microfrontend 契约

- Route：shell 拥有 `/billing/**` 前缀；remote 只请求相对导航，deep link/404 双方 contract test。
- Identity：shell 提供短期 session capability/用户公开上下文；remote API 每次服务端鉴权和对象授权，不能信 tenant event。
- Event：版本化 schema，只发 `invoice.paid` 等事实/导航意图；无任意对象/PII。
- Version：manifest 声明 `requiredShellRange`；保留 N/N-1 兼容，发布前跑双向矩阵。
- Failure：超时、chunk 404、runtime error 有局部 error boundary/fallback；shell 可 pin 上一 remote。
- UI：共享 semantic tokens；CSS namespace/Shadow 边界；overlay/focus stack 与 shell 协议；键盘跨边界可完成任务。
- Security：CSP、允许的 entry origin、SRI/签名策略、CSRF、依赖扫描；remote 不获得服务 secret。
- Performance：入口/共享依赖/加载超时/RUM 预算；按真实下一步预取，不阻塞关键路由。
- Observe：app/release/shell version/trace id，统一错误 owner；source map 按 release 上传。

```ts
type BillingEventV1 =
  | { version: 1; type: 'billing.navigation-requested'; to: string }
  | { version: 1; type: 'billing.invoice-paid'; invoiceId: string }

export function parseBillingEvent(value: unknown): BillingEventV1 {
  return billingEventSchema.parse(value) // 运行时 schema；失败拒绝并记录低基数错误
}
```

### 6. 契约与回滚测试

1. manifest schema/version/integrity 校验；
2. old shell + new remote；
3. new shell + old remote；
4. remote chunk 404 显示局部 fallback；
5. remote 加载超时后不阻塞全局导航；
6. runtime render error 被边界捕获并含 owner/release；
7. deep link、back/forward、404 和 base path；
8. session 到期/撤销后 remote 不能继续访问 API；
9. 篡改 tenant/event 不能越权；
10. CSS/overlay/z-index/focus/Tab/Escape 组合；
11. Vue/shared dependency 版本不支持时拒绝加载而非随机崩溃；
12. 性能预算、弱网重试和离线；
13. canary pin 回上一 remote，进行真实演练；
14. orders+customers+billing 的兼容 API 跨版本旅程。

若半年后 80% billing 发布仍与 orders 同步，说明独立部署价值未兑现。检查是业务天然同边界、API 不兼容、组织划分错误还是遥测口径错误；若长期强一致且共同变更，ADR 可被“合回 package/重新划 aggregate boundary” supersede，而不是为保住架构面子继续付费。

## 题 2 参考答案：Vue 2 Strangler + Custom Element

### 1. 盘点与策略组合

先以页面为行，记录：流量、退款/资金风险、变更频率、Vue2-only API、全局依赖、测试、owner、错误率、性能和可回滚性。退款是高风险、低测试，应先做 characterization，不是先迁；低风险高变更页面先做 Vue 3 路由切片。

组合建议：

- 兼容构建作为短期桥，帮助通用组件从 Vue 2 语义过渡；有明确退出日期。
- 新业务/低耦合页面按路由进入 Vue 3.5 app；session/导航用窄 adapter。
- 无法立即改路由的局部区域用 Vue 3 island，但限制每页 root 数和重复 runtime。
- 聊天 widget 用 custom element 服务 React/legacy 宿主。
- 不做一次性 rewrite；不让所有 180 页永久跑双 runtime；不以 Vapor 为迁移前提。

### 2. 12 个月 roadmap

| 月份 | 产出 | 验收/回滚 |
| --- | --- | --- |
| 1–2 | inventory、支持矩阵、生产指标、退款 characterization、统一 release/trace | 关键流程可重放；无行为改变，可直接回滚工具链 |
| 3–4 | API/schema ACL、event adapter、Vue3 shell/route pilot、design token bridge | pilot flag 关闭即回旧页；错误/完成率不劣化 |
| 5–6 | 低风险高变更页面切片；聊天 CE canary | old/new contract + a11y/perf；CE 可 pin 旧版本 |
| 7–8 | 客户/工单 vertical slices；迁移 mixin/event bus 为 composable/typed event | 每个 adapter 有使用量、owner、删除条件 |
| 9–10 | 退款先影子读/对照，再小比例 Vue3 UI；命令仍幂等服务端校验 | 金额/权限/重复提交零差异；一键路由回 Vue2 |
| 11 | 退款扩大灰度；删除已无调用 legacy slice | 旅程、错误、性能、客服效率达预算 |
| 12 | 默认 Vue3.5；清兼容构建/旧库/flag，保留审计与回滚制品 | legacy route 0 或有批准延期 ADR |

每个 flag 记录 owner、创建日、到期日和删除 PR。双写只用于能证明幂等/对账的状态；资金命令不可随意双写。

### 3. Anti-corruption layer

```ts
interface LegacyRefundDto {
  refund_id: number
  status: 0 | 3 | 7 | 9
  amount_yuan: string
  updated_at: string
}

type RefundState =
  | { type: 'requested' }
  | { type: 'reviewing' }
  | { type: 'approved' }
  | { type: 'rejected' }

interface Refund {
  id: string
  state: RefundState
  amountCents: number
  updatedAtIso: string
}

export function mapLegacyRefund(dto: LegacyRefundDto): Refund {
  const stateByCode: Record<LegacyRefundDto['status'], RefundState> = {
    0: { type: 'requested' },
    3: { type: 'reviewing' },
    7: { type: 'approved' },
    9: { type: 'rejected' },
  }
  const amountCents = parseMoneyToCents(dto.amount_yuan) // 使用十进制安全实现
  if (!Number.isSafeInteger(amountCents) || amountCents < 0) {
    throw new Error('Invalid refund amount')
  }
  return {
    id: String(dto.refund_id),
    state: stateByCode[dto.status],
    amountCents,
    updatedAtIso: new Date(dto.updated_at).toISOString(),
  }
}
```

事件协议：

```ts
type RefundEvent =
  | { version: 1; type: 'refund.requested'; refundId: string; occurredAt: string }
  | { version: 1; type: 'refund.approved'; refundId: string; occurredAt: string }
  | { version: 1; type: 'refund.rejected'; refundId: string; reasonCode: string; occurredAt: string }
```

在 legacy adapter 用 schema 把旧 bus payload 转换成这一联合；新代码只消费已验证事件。未知 version/code 拒绝并告警，不静默猜。

### 4. 聊天 Custom Element 契约

```ts
interface ChatWidgetProperties {
  conversationId: string
  locale: string
  theme: 'light' | 'dark'
  authProvider: () => Promise<{ accessToken: string; expiresAt: number }>
}

type ChatWidgetEvent =
  | { type: 'ready'; version: 1 }
  | { type: 'message-sent'; version: 1; messageId: string }
  | { type: 'auth-required'; version: 1 }
  | { type: 'fatal-error'; version: 1; code: string }
```

- 简单字符串用 attributes；对象/函数如 `authProvider` 用 property，不写进 HTML。
- token 由 host 回调按需提供短期值，CE 不持久化，不通过 event detail 回传。
- 事件 `bubbles/composed`，React host 对 `event.detail` runtime validate；卸载时移除 listener。
- Shadow DOM 可隔离 legacy CSS；主题通过少量 documented CSS custom properties，overlay 明确在 shadow 内还是 host portal。
- 每个 CE 构建内嵌 Vue runtime 可提高宿主独立性但增加包体；单 widget 可接受时记录预算。不要假设 React host 有 Vue singleton。
- manifest/元素 API 版本化，支持 N/N-1；加载失败显示 host fallback，错误带 widget release/trace。
- server 仍鉴权/授权；conversation id 和事件都不可信。

React 宿主用 `ref` 设置 property 并通过 `addEventListener` 消费标准 CustomEvent，而不是依赖 React 对未知复杂 property 的偶然映射。

### 5. 版本支持与发布

维护一张版本化矩阵：Vue 3.5.x、对应 Router/Pinia/Vite、组织批准的 Node LTS、浏览器基线、UI 库与 TypeScript。每月自动依赖 PR；patch/security 分组并跑全矩阵，minor 先 canary，major 用 RFC/迁移分支。lockfile 可重现；制品和 remote 可 pin；每次升级记录 changelog 风险、bundle/SSR/type/test 结果和回滚版本。

避免在同一 release 同时升级 Vue、Router、构建插件并迁退款页。这样出错时没有可识别变量。

### 6. Vapor spike

它与 legacy 迁移解耦，单独 timebox 两周：

1. 选择非资金、性能敏感且有完整测试的代表 fixture，如 5,000 行聊天历史；
2. 固定 Vue 3.5 stable 对照，另建 3.6 RC + opt-in Vapor 实验，不改业务契约；
3. 比较 DOM/ARIA、事件、third-party components、Devtools、error handling、SSR/hydration、bundle、mount/update CPU、memory；
4. 弱机重复测并保存版本/trace，不只引用官方 benchmark；
5. stop 条件：API/库不支持、correctness 差异、SSR/工具链阻塞、收益低于预算、无法一键回退；
6. 结论可为等待稳定版。RC 更新后重跑，不能把 spike 结果直接推广到退款。

Vapor 是编译/渲染策略，不会替你解决 Vue2 global bus、DTO、授权和业务测试；因此“免得迁两次”是错误因果。

### 7. 测试与观测

- characterization：根据生产事故/客服操作，锁定退款金额、权限、状态转换、重复提交、超时恢复和审计行为；先不宣称旧行为都正确，标记已知 bug。
- contract：legacy DTO/event → 新 union；未知 code/version；old/new route session/navigation。
- browser/E2E：Vue2 shell + Vue3 island/route + CE + React host；focus、overlay、IME、复制粘贴。
- dual-run：只读计算 shadow compare，输出匿名差异；资金 command 由单一主路径处理。
- canary：按客服组/租户，监控退款完成率、金额差异、重复率、错误、耗时、回退。
- observability：framework slice、release、route、flag、adapter version、trace；不记录聊天/退款敏感正文。
- cleanup：adapter 使用量为 0、连续稳定窗口、回滚制品仍可用后删除；删 flag 和旧代码一起验收。

第 8 月仅完成 45% 不自动代表失败。若错误率与交付显著改善，先看剩余页面的业务价值/复杂度、双栈运行成本、adapter 增长、支持矩阵和风险集中度。可延长高价值迁移、砍掉低价值“为了百分比”的页面，或给延期 ADR；若双栈事故/维护成本抵消收益则缩范围。补采每切片工时、变更频率、故障、用户任务、旧依赖阻塞和删除速度。

## 复写检查

合上答案后应能独立产出：

1. 模块化单体目录与 CI dependency rules；
2. 有 rejected options/negative consequences/revisit 的 ADR；
3. 微前端 route/identity/version/failure/security/a11y 契约；
4. 12 个月 strangler 路线和 adapter 删除闸门；
5. legacy DTO/event 的 anti-corruption layer；
6. custom element 的 property/event/auth/version 边界；
7. Vue 3.5 对照下的 3.6 RC/Vapor 隔离实验。
