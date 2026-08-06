# 第 13 章参考答案

答案把“SDK 编排”和“企业控制面”分开：Agents SDK 负责 Agent、function tool、结构化输出和运行；模型路由、tenant policy、权限与写操作审批仍由自己的代码控制，避免换框架时丢掉安全边界。

## 可运行标准答案

- [离线多模型路由器](./reference/solution.py)
- [真实 OpenAI Agents SDK 集成](./reference/agents_sdk_integration.py)
- [自动化测试](./reference/test_solution.py)
- [运行说明](./reference/README.md)

