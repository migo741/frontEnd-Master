# 第 19 章参考答案

答案把安全控制写到了代码层：URL 默认拒绝内网/非 HTTP(S)、workspace 路径防逃逸、归档解压预算、模型输入与权限分离，以及一个仅供本地学习的受限 Python runner。后者不是强隔离；真实不可信代码必须运行在独立容器/微虚机中，禁用 host mount、凭据和默认网络。

## 可运行标准答案

- [安全策略与本地 runner](./reference/solution.py)
- [自动化红队测试](./reference/test_solution.py)
- [运行说明](./reference/README.md)

