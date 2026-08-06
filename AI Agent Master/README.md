# AI Agent Master：从前端工程师到生产级智能体开发者

> 调研与编写日期：2026-08-04  
> 适合你：JavaScript、Vue 3、TypeScript 已有中级基础；Python 和 Agent 经验可以从零开始。

这套指南的目标不是教你“套一个 LangChain 聊天机器人”，而是让你能设计、实现、评测、上线和治理生产级 Agent：模型输出不确定时仍可控，工具产生副作用时仍安全，长任务失败后可恢复，质量与成本有数据闭环。

## 主语言结论

主线选择 **Python**，TypeScript 作为前端、Node 集成和跨语言 MCP 的辅助语言。

原因不是“AI 只能用 Python”，而是 2026 国内岗位样本中 Python 覆盖最稳定，LangGraph、PyTorch、LlamaIndex、AutoGen、Pydantic/FastAPI 等岗位高频生态以 Python 为主。Java、Go、TypeScript 也有真实岗位，但更多服务于既有企业后端、高并发基础设施或全栈产品。

课程先用 4 章补齐 Python，不要求你先去学一整套传统 Python 大全。

## 从哪里开始

1. 阅读 [市场调研与能力地图](./00-市场调研与能力地图.md)。
2. 阅读 [学习方法与版本策略](./00-学习方法与版本策略.md)，建立练习仓库和评测纪律。
3. 按 01 → 22 顺序学习。每章固定为：`00-讲义.md` → `01-练习/README.md` → `02-答案/README.md`。
4. 先独立做练习，再看答案；照答案完成后，关掉答案从空文件复写关键部分。
5. 从第 05 章开始维护同一个 Agent 实验仓库；第 22 章将所有能力收束成毕业项目。

## 版本策略

- Python 教学主线：**3.13**；CI 兼顾 3.12 和当前稳定 3.14。Python 3.15 在调研日仍是预发布，不作为生产基线。
- Python 官方文档在调研日已发布 3.14.6；选择 3.13 是兼顾现代语法与第三方生态成熟度，不是继续使用旧语法。
- 使用 `pyproject.toml`、`uv`、Ruff、Pyright 或 mypy、pytest、Pydantic v2、FastAPI。
- Agent 框架采用“先手写循环，再学框架”：重点实践 LangGraph 与 OpenAI Agents SDK，同时会比较 PydanticAI、Google ADK、Claude Agent SDK 的边界。
- 不在代码中永久写死“最新模型名”；通过配置、能力矩阵和 eval 选择模型。升级前运行固定数据集。

官方入口：[Python 3.14 文档](https://docs.python.org/3.14/whatsnew/)、[Python 版本状态](https://devguide.python.org/versions/)、[OpenAI Agents SDK](https://developers.openai.com/api/docs/libraries#use-the-agents-sdk)、[LangGraph](https://docs.langchain.com/oss/python/langgraph/overview)。

## 22 章路线

| 阶段 | 章节 | 目标 |
|---|---:|---|
| Python 前置 | 01–04 | 语法、数据模型、类型、Pydantic、异步和工程化 |
| Agent 原理 | 05–10 | LLM 边界、结构化输出、Prompt、工具循环、状态与记忆 |
| 知识与编排 | 11–16 | RAG、LangGraph、Agents SDK、MCP、多 Agent、持久执行 |
| 生产质量 | 17–21 | Evals、观测、成本、安全、部署与高级 Agent |
| 综合验收 | 22 | 企业知识工作 Agent、系统设计和面试答辩 |

## 每章通过标准

- 能说明该机制解决什么，不能解决什么。
- 练习一独立完成；练习二至少完成设计、看答案后复写核心路径。
- 同时有确定性单元测试、Agent eval 和失败用例，不能只“手动聊着感觉不错”。
- 所有外部输入先验证；所有写操作有权限、幂等、审批或补偿策略。
- 能解释不用 Agent、少用模型或改成普通代码时为何更好。

## 你最终应具备的能力

- 手写受预算约束的 tool-calling loop，理解框架背后的状态机。
- 用结构化输出、Pydantic 和契约测试连接模型、工具和业务系统。
- 设计 RAG、memory、checkpoint、HITL、multi-agent，并知道何时不用它们。
- 建立离线/在线 eval、trace、质量门槛、成本与延迟预算。
- 防御 prompt injection、越权工具、数据泄漏、恶意 MCP 和危险代码执行。
- 以 FastAPI、队列、PostgreSQL/Redis、容器和可观测性上线长任务 Agent。
- 评审框架和模型升级，不被某个厂商 SDK 锁死。

## 进度表

- [ ] 01 Python 语法与数据模型
- [ ] 02 Python 函数、迭代器与资源管理
- [ ] 03 Python 类型系统与 Pydantic
- [ ] 04 Python 异步并发与工程化
- [ ] 05 LLM 与 Agent 基础
- [ ] 06 模型 API、结构化输出与流式交互
- [ ] 07 Prompt 与 Context 工程
- [ ] 08 工具调用与手写 Agent 循环
- [ ] 09 工具工程与外部系统集成
- [ ] 10 状态、记忆与上下文压缩
- [ ] 11 RAG 检索增强与知识库
- [ ] 12 LangChain 与 LangGraph 编排
- [ ] 13 OpenAI Agents SDK 与多模型适配
- [ ] 14 MCP 协议与工具生态
- [ ] 15 规划、反思与多 Agent 协作
- [ ] 16 HITL、持久执行与幂等
- [ ] 17 Evals、测试与质量闭环
- [ ] 18 可观测性、成本与性能
- [ ] 19 Agent 安全、隐私与沙箱
- [ ] 20 生产架构、部署与运维
- [ ] 21 浏览器、代码、研究与多模态 Agent
- [ ] 22 毕业项目、系统设计与面试

## 三条纪律

1. 模型说“成功”不等于工具真的成功；只信系统状态和已验证结果。
2. Prompt 不是安全边界；授权、隔离、审批和审计必须由代码与基础设施执行。
3. 多 Agent 不是默认升级；单 Agent + 明确工作流能解决时，不增加协作不确定性。
