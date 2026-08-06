# 第 08 章练习

## 练习一：状态归属审计

某后台把以下内容全部放在一个 Redux slice：

- 当前 URL 的 page/sort/query；
- 从 `/api/orders` 获取的 orders 和 loading/error；
- 编辑订单弹窗的输入草稿；
- 当前登录用户、HttpOnly session、access token 镜像；
- 左侧栏展开；
- 跨三个步骤的未提交报价单；
- toast 队列；
- WebSocket connection 实例；
- 10 万条表格行的 hover id；
- 离线待同步 mutation。

任务：逐项决定 URL / Query / form / local / external store / ref/service 的归属，说明生命周期、权威源、持久化和安全。画迁移路线，要求不中断现有功能、可灰度回滚。

验收：不能只写“看情况”；每项至少给一个可验证理由。

## 练习二：协作任务板的 Redux Toolkit 模型（高难）

场景：项目有 columns/tasks/users；拖拽任务、多人 WebSocket patch、离线操作队列、undo 最近一次本地移动。

要求：

- 用 `createEntityAdapter` 规范化实体；同一 task 只有一个权威副本。
- action 表达 `taskMoveRequested/Confirmed/Rejected` 等领域事实。
- 本地 optimistic move 带 operationId/baseVersion；远端 patch 不得静默覆盖本地 pending。
- selector 只为目标 column 组合 task，并保持无关 column 更新隔离。
- WebSocket 实例不进 Redux；中间件/service 将外部事件翻译为 action。
- Redux state 可序列化；DevTools 可读；持久化队列带 schema version。
- 写 reducer/selector/冲突测试。

不要实现完整 UI。核心产物是模型、事件协议、冲突策略和测试。

