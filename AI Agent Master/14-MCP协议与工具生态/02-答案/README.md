# 第 14 章参考答案

实现一个带严格 schema、分页、结果上限、tenant ACL、rate limit、audit 的只读工单服务，并给出真正可启动的 Python MCP Server 与 TypeScript contract client。写操作应继续复用第 09/16 章 proposal → approval → idempotent execute，而不是把数据库写权限直接交给模型。

## 可运行标准答案

- [安全业务内核](./reference/solution.py)
- [Python MCP Server](./reference/mcp_server.py)
- [TypeScript contract client](./reference/typescript_consumer.ts)
- [自动化测试](./reference/test_solution.py)
- [运行说明](./reference/README.md)

