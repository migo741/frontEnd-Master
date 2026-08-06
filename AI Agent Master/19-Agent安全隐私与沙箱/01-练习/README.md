# 第 19 章练习

## 练习一：威胁模型与红队

对“能读内部知识、搜索 Web、发邮件、运行 Python”的研究 Agent 做 assets/actors/trust boundaries/data flows/abuse cases/controls。

实现至少 30 条红队 case：间接注入窃取知识、恶意 MCP、SSRF、跨租户、邮件外发、路径逃逸、压缩炸弹、无限输出、approval 欺骗。给每项预防/检测/响应和残余风险。

## 练习二：代码执行沙箱设计（高难）

设计并原型一个执行用户/模型 Python 的沙箱 API：输入文件、代码、资源预算、网络 policy、产物。不得挂 host Docker socket/家目录/API key。实现 timeout/output/path 限制；写出容器仍不能抵挡的威胁和更强隔离升级路径。
