# 第 06 章参考答案

业务代码只依赖统一 request/event/error。capability 在请求前检查；模型流产生任何增量后，不做会导致重复 token 或工具的透明重试。应用事件日志恢复已观察事件，不虚构供应商 token 级续传。

## 可运行标准答案

- [模型网关与事件回放](./reference/solution.py)
- [自动化测试](./reference/test_solution.py)
- [运行说明](./reference/README.md)

