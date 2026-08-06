# 第 20 章练习

## 练习一：生产化设计

把前述客服 Agent 设计为 100 tenant、日 10 万 run、峰值 50 RPS、最长 24 小时等待审批。给出组件、表结构、queue、worker、SSE、存储、限流、SLO、容量、部署、DR 和 10 份 runbook 标题。

必须处理滚动升级中的旧 run、重复消息、provider 限额、tenant fairness、数据地域和写工具 kill switch。

## 练习二：Game Day

在本地/测试环境注入：模型 429 30 分钟、DB 慢、queue 重复、worker crash、RAG 旧索引、坏 Prompt 灰度、trace backend 泄漏风险。记录检测时间、止血、恢复、数据一致性和改进项。
