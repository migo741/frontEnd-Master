# 答案与评审清单

毕业题没有唯一代码答案，使用下列门禁自评。任何“是”都必须能指向代码、测试、trace 或 ADR，而不是口头声明。

## 架构

- URL、组件、Pinia、query cache 的状态所有权是否明确？
- feature 是否只通过 public API 依赖？是否有规则自动阻止深层 import？
- ADR 是否包含被否决方案、代价和复审条件？

## 正确性

- 搜索迟到响应、卸载写状态、重复提交、401 风暴、409 冲突是否各有确定测试？
- loading/error/data 是否用状态机避免非法组合？
- Router 首次深链、登出清路由、切租户是否正确？

## 质量与体验

- 测试是否主要通过可访问角色和用户行为断言？
- Combobox/Dialog 能否全键盘完成，焦点是否恢复？
- loading、empty、error、长文本、慢网和离线是否有产品化处理？

## 性能和运维

- 优化前后是否是同场景 trace？是否同时有 lab 与 RUM 计划？
- bundle、LCP、INP、CLS 是否有预算和 CI/发布后验证？
- error event 是否包含 release、route、requestId，且不含 token/隐私？

## 模拟面试参考骨架

原理题先讲 track/trigger、effect scheduler、render function/VNode、patch 与 DOM，再用批处理和 key 事故举证。系统题先问数据规模、更新频率、交互、设备和 SLO，再谈服务端分页/聚合、窗口化、稳定 props、worker、背压和测量。架构题先证明问题是否存在，不因为题目给出“微前端”就默认采用。

## 最终复写

关闭所有答案，重新实现 `useLatestTask`、single-flight refresh 和一个带类型的状态 union；再用 15 分钟讲清三者共同解决的核心：显式状态、并发所有权和失败恢复。如果能写但讲不清，还没有达到高级工程师的方案沟通标准。

