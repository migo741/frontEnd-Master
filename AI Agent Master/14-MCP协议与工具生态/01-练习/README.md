# 第 14 章练习

## 练习一：只读工单 MCP Server

用 Python SDK 暴露搜索/读取工具和知识 resources；tenant/user 从认证 context 获取。实现 stdio dev 和远程 production 设计，严格 Schema、分页、响应上限、ACL、rate limit、audit。

写 Python 与 TypeScript 两个 contract client；测试 list/call/cancel/未知工具/恶意查询/跨租户/超大结果。固定 SDK 版本并记录协议兼容矩阵。

## 练习二：安全写工具（高难）

新增评论/状态变更 MCP tools，设计 proposal、approval、execute 分层。模拟恶意 server/tool description、恶意工单正文、过度参数、审批后篡改和 token audience 错误。写完整威胁模型和红队用例。
