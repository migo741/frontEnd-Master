# 第 11 章练习

## 练习一：多租户企业知识库

用至少 50 份混合 Markdown/PDF/表格文档构建 RAG：增量 ingestion、结构 chunk、hybrid retrieval、rerank、ACL、citation、删除和版本。

建立 60 条 dataset，包含无答案、版本冲突、精确编号、表格、多跳、恶意文档、跨租户。分别报告 retrieval 与 answer 指标，不能只报最终 LLM 分。

## 练习二：诊断 RAG 事故（高难）

给出 10 条错误回答和完整 trace，逐条归因 ingestion/retrieval/rerank/context/prompt/model/citation/ACL/freshness。每条提出最小修复和能防回归的测试；禁止统一回答“换更大模型”。
