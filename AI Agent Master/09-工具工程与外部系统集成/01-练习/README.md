# 第 09 章练习

## 练习一：企业工单工具集

为工单 Agent 设计 8 个工具：搜索、读取、评论提案、状态变更提案、指派、知识查询、附件摘要、通知。完成风险分级、Schema、权限矩阵、幂等、审计和错误协议。

要求：跨 tenant 永远不可见；评论/状态/通知需按风险审批；附件和评论视为不可信；用 15 个恶意 tool call 做 contract tests。

## 练习二：安全数据分析工具（高难）

实现受限 analytics query，不直接暴露 SQL。模型选择 dataset、dimensions、metrics、filters、time range；服务端编译参数化 SQL。限制 tenant、PII、基数、行数、扫描量和时间。与直接 text-to-SQL 方案做威胁/能力比较。
