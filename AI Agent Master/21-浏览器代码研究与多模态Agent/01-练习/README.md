# 第 21 章练习

## 练习一：有引用的研究 Agent

构建研究 Agent：规划、并行只读搜索、抓取、安全提取、去重、source quality/freshness、claim-evidence graph、引用报告。不得拥有邮件/私库写权限。

数据集含 20 个问题、冲突来源、过时页面、SEO 垃圾、恶意注入和无答案。评 citation support、source quality、coverage、cost、P95 和 injection resistance。

## 练习二：代码修复 Agent（高难）

在一次性 sandbox 中完成 issue → repo inspection → patch → tests → review report。工具限制 workspace、网络和命令；禁止读取 secret/推送。测试 crash、超时、恶意仓库 instructions、依赖投毒、测试伪通过和大 diff。最终状态由测试/策略验证器决定。
