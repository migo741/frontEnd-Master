# 第 07 章练习

## 练习一：客服 Agent Prompt 重构

把一个 1,500 行、混合政策/FAQ/示例/用户历史的 system prompt 拆为：稳定政策、任务模板、Schema、按需知识检索、结构化会话摘要和工具目录。

建立 30 条 eval：正常、歧义、越权退款、恶意 FAQ、历史冲突、缺证据、长会话。比较重构前后任务成功、注入成功率、token、延迟和拒绝率。

## 练习二：Context Builder

设计纯函数 `build_context(run_state, task, budget)`：选择必要消息、事实 ledger、证据、工具和 policy；超预算按确定优先级压缩；每个片段有 source/trust/freshness/token estimate。禁止把 secret 和其他 tenant 数据带入。
