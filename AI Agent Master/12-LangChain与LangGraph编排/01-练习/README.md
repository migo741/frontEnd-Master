# 第 12 章练习

## 练习一：邮件工单图

构建：读取邮件 → 分类 → 搜知识/查客户（可并行）→ 拟回复/操作提案 → 高风险人工审批 → 执行 → 完成。

要求：typed state、持久 checkpointer、retry/error 路由、SSE 应用事件、approve/edit/reject、thread 隔离。用故障注入验证审批前后 crash 不重复发送/变更。

## 练习二：从手写 Runtime 迁移到 LangGraph

迁移第 08 章 runtime，列出保留在 domain、交给 framework、必须自定义的部分。比较代码量、trace、恢复、测试、锁定成本和性能；如果某能力退化，应保留手写方案而非强行迁移。
