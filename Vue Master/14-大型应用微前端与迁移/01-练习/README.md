# 第 14 章练习：让架构选择经得住证据

> 本章恰好两题。必须比较替代方案、写负面后果与回退，不接受只画“高级架构图”。

## 题 1：先救模块边界，还是立刻上微前端？

### 背景

一个 Vue 3.5 SaaS 有 45 名开发者、订单/客户/计费/工单四个业务域，单仓库、每周发布两次。问题包括：任何模块都能 import 任意 store；共享 `api.ts` 返回 `any`；一次修改触发全仓测试 70 分钟；订单结算经常要求客户与计费同版本原子上线。

管理层提出按四个域立刻拆四个 runtime microfrontend，目标“三个月后每天独立发布”。但实际只有计费团队长期独立；其他三个团队每周有跨域需求。平台团队只有两人，当前没有契约测试、统一 observability 或动态 remote 回滚能力。

### 交付物

1. 画出现状依赖与目标模块化单体目录；写 domain/application/infrastructure/ui/public 的依赖规则。
2. 给出能在 CI 执行的边界规则、增量构建/测试与 ownership 方案。
3. 比较：维持现状、模块化单体、package 化、四个微前端、仅计费微前端；至少 8 个决策维度。
4. 写一份 ADR，明确决定、反对意见、负面后果、90 天里程碑、量化验收和复查触发器。
5. 若最终只提取计费，定义 shell/计费间 route、identity、events、version、failure、CSS/a11y、security、performance 和 observability 契约。
6. 写至少 10 条 contract/组合/回滚测试；包含 remote 超时、旧 shell+新 app、新 shell+旧 app 和会话撤销。

### 约束

- 前 30 天不能停止业务发布；
- 服务端仍必须做对象级授权；
- 不允许 shell 变成跨域全局 store；
- 必须保留订单+客户+计费原子变更能力，直到有兼容 API 证明可拆；
- 方案要写“不做什么”。

### 发散追问

若 6 个月后计费已独立，但 80% 发布仍与订单同步，你会合回、保留还是重新划边界？什么证据会触发 ADR supersede？

## 题 2：Vue 2 核心系统的渐进迁移与 Vapor 评估

### 背景

一个运行 7 年的 Vue 2 客服系统有 180 个页面、Vuex 3、旧 Router、webpack 私有插件、全局 event bus、mixins、class components 和一个不再维护的 UI 库。每天 30,000 名客服使用，不能停机重写。最关键的“退款”流程没有自动化测试，只有生产事故记录。

团队希望：12 个月迁到 Vue 3.5；其中聊天 widget 还要嵌入 React 宿主；同时有人建议直接使用 Vue 3.6 RC 的 Vapor Mode，以免“迁两次”。

### 交付物

1. 做风险/价值盘点表，并选择兼容构建、路由切片、Vue 3 island、custom element 的组合；说明不用的选项。
2. 写 12 个月 strangler roadmap，每阶段有用户行为基线、功能 flag、数据/事件契约、验收、回滚和 legacy 删除条件。
3. 为退款 DTO 写 anti-corruption layer；为新旧 event 写版本化判别联合和 runtime validation 方案。
4. 设计聊天 custom element 的 attributes/properties/events、样式隔离、Vue runtime、auth、错误与版本契约；React 宿主如何安全消费。
5. 制定 Vue/Router/Pinia/Vite/Node/浏览器支持矩阵与依赖升级发布策略。
6. 单独写一份 Vapor spike 计划：为何它不是迁移前提、怎样选 fixture、比较哪些 correctness/performance 指标、何时停止/等待稳定版。
7. 给出测试与观测矩阵，特别覆盖退款的 characterization test、双栈组合与生产灰度。

### 约束

- 生产默认仍为 Vue 3.5 稳定路径；
- Vue 3.6 RC/Vapor 只能在隔离实验，不得承载退款主路径；
- 不能让新代码直接理解 legacy `status=7` 等魔法值；
- 每个 adapter/flag 要有 owner 和删除日期；
- 不能把 token 交给 custom element/浏览器宿主。

### 发散追问

迁移到第 8 个月，业务只完成 45%，但错误率下降 35%、交付速度提升 20%。你会延长双栈、缩范围还是暂停？写出数据不足时需要补采的证据。
