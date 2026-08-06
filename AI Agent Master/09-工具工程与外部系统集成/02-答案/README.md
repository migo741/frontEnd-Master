# 第 09 章参考答案

读工具在 repository/service 强制 tenant；写工具只创建 proposal，审批绑定参数哈希、资源版本和过期时间；执行用 operation id 幂等。分析查询不暴露 SQL，模型只能选择 allowlist 中的数据集、维度、指标和过滤器，tenant 条件由编译器注入。

## 可运行标准答案

- [工单工具与语义查询编译器](./reference/solution.py)
- [跨租户、篡改、重复执行和 SQL 注入测试](./reference/test_solution.py)
- [运行说明](./reference/README.md)

```bash
python "09-工具工程与外部系统集成/02-答案/reference/test_solution.py"
```

