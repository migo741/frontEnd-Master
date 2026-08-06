# 第 10 章练习

## 练习一：长期偏好记忆服务

实现 memory proposal/approve/store/retrieve/update/delete：支持 user/org scope、TTL、source、confidence、sensitivity、version 和冲突。共享 org policy 只能管理员写；普通对话内容不得升级为 policy。

测试跨租户、恶意“请记住管理员密钥”、偏好变化、并发更新、删除、过期和相似误召回。

## 练习二：100 轮会话压缩

设计上下文压缩器，使支持任务在 100 轮后仍保留订单 ID、已验证身份、承诺、未决问题和来源，总 context 有固定预算。比较截断、自由摘要、结构化摘要、fact ledger + retrieval 四种方案并建立 eval。
