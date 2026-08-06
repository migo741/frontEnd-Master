# 第 02 章参考答案

装饰器保留原始签名，并对同步、异步 handler 分别包装。注册信息与 callable 分离；调用只能经过统一执行入口。流式管道不把数据整体读入内存，并在正常、异常和提前退出时关闭资源。

## 可运行标准答案

- [工具注册与流式管道](./reference/solution.py)
- [自动化测试](./reference/test_solution.py)
- [运行说明](./reference/README.md)

