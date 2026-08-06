# 第 20 章参考答案

答案把 100 tenant 的公平调度、去重入队、provider 熔断、Prompt 灰度/回滚和最小 FastAPI 接入写成代码，并给出容器化本地拓扑。业务状态不放在 Web 进程内；示例内存实现只是可执行 contract，生产要替换为 PostgreSQL、队列和 durable workers。

## 可运行标准答案

- [生产控制面内核](./reference/solution.py)
- [FastAPI 接入](./reference/app.py)
- [Dockerfile](./reference/Dockerfile) / [Compose](./reference/compose.yaml)
- [自动化测试](./reference/test_solution.py)
- [运行说明](./reference/README.md)

