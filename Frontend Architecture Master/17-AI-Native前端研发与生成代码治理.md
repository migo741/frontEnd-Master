# 第 17 章：AI-native 前端研发与生成代码治理

> 版本说明：模型、IDE、MCP 与 Agent 能力按 **2026-08-16** 理解。变化最快的是工具能力；稳定责任仍是人定义目标、边界、证据和上线决策。

## 本章要解决的市场与业务问题

AI Coding 已从补全单行走向读仓、改多文件、运行测试和操作环境。它能放大良好工程，也会更快复制错误边界、过时依赖和未经理解的模式。

美团技术团队 2026 年公开的 31 万行代码重构实践指出：当 90% 以上代码由 AI 辅助生成，没有统一规范会加速腐化；工程师的工作重心转向设计并维护一个让 AI 可靠产出的工程环境。

### 非目标

- 不重复 Prompt、RAG、手写 Agent 或模型 API 教程；
- 不以生成代码行数衡量生产率；
- 不要求 AI 替代架构、Code Review 和责任人，也不让 Agent 默认读取全部仓库、秘密和内网；
- 不把测试通过等同于需求正确；
- 不以单次 benchmark 直接更换模型，也不宣称本章解决版权与劳动法判断。

## 1. 区分三个层次

**AI-assisted**：人主导任务，AI 提供补全、解释或局部修改。

**Agentic workflow**：AI 在受限环境中规划、读写、调用工具和验证多步任务。

**AI-native SDLC**：仓库结构、知识、政策、平台 API、评测和审批被设计为人和 Agent 都能安全消费。

会安装插件属于第一层；能治理第二层并建设第三层，才形成平台和架构能力。

## 2. 参考架构

```text
Intent / Issue / Design
  → Context service（代码图、文档、owner、历史、契约）
  → Rules + Skills + Tool/MCP registry
  → Model/Agent runtime
  → Isolated workspace + scoped identity
  → diff / artifact / provenance
  → deterministic checks + task eval + human review
  → Pre-PR / PR / rollout / production feedback
```

横向控制面管理模型、预算、权限、数据、版本和审计；证据面记录上下文、工具、变更、验证和批准。

Agent 不是 policy enforcement point。身份、授权、网络、文件、发布和秘密由确定性代码与基础设施执行。

## 3. 仓库首先要对人清楚

AI 无法修复混乱的真实所有权。仓库至少需要：

- 明确模块和依赖方向；
- 可发现的 build/test/lint 入口与小而稳定的公共 API；
- 运行时 Schema 和错误语义；
- owner、ADR、迁移、兼容说明及可重复环境与锁定依赖；
- 关键不变量和高风险目录；
- 禁止访问的数据与动作。

如果资深工程师也说不清目标，Rule 写得再长只会把分歧自动化。

## 4. Context 是受治理的数据产品

有效上下文不是整仓文本，而是当前任务所需的最小、可信、新鲜信息。

Context service 可以组合：

- symbol、依赖和调用图；
- package/route/owner/service catalog；
- 需求、ADR、接口、Schema、测试、CI、事故和生产使用；
- 迁移状态、版本和 deprecation；
- 安全分类、工具权限及相关而非全部历史 diff。

每个来源要有 owner、更新时间、ACL 和 provenance。README、Issue、网页、依赖文档都可能过时或包含恶意指令。

检索到的内容是数据，不自动成为高优先级指令；指令层级与引用边界必须由 host 强制。

## 5. Rule：把已对齐约束变成可执行入口

Rule 适合表达始终成立的仓库约束：目录边界、命令、禁止动作、Schema、测试和安全要求。

高质量 Rule 应：

- 由团队先形成共识；
- 小而分层，按目录/任务加载；
- 有 owner、版本、变更评审和到期，并指向权威文件而非复制文档；
- 能被 lint、test 或 policy 验证；
- 明确冲突与优先级，并用失败案例测试是否真的约束行为。

数万字“万能 Rule”会造成 context rot，关键约束反而被淹没。

## 6. Skill：封装可复用工作流

Skill 适合迁移、发版、生成组件、排查性能等有稳定步骤和证据要求的任务。

一个可治理 Skill 包含：适用条件、输入、允许工具、步骤、停止条件、验证、输出、失败恢复、owner 和版本。

先由主责工程师跑通一条真实路径，再提炼 Skill；不要让 AI 根据理想流程凭空生成组织 SOP。

Skill 也属于供应链：可被污染、过时或过度授权，需要 review、测试、签名/来源和使用清单。

## 7. Tool / MCP 是能力边界

MCP 等协议能统一发现与调用，不会自动带来可信、幂等和授权。

工具设计要求：

- 小而明确的动作与 Schema；
- 身份从可信 host 注入，不由模型填写；
- resource/tenant/action 在执行端授权，读、写、发布、删除分级；
- deadline、幂等、审计和稳定错误；
- 结果最小化，不返回整库或秘密；
- 高风险参数预览并由人确认，capability 可发现、可撤销、可版本化。

“万能内部工具”拥有所有系统权限，是最危险的便利。

## 8. 沙箱与最小权限

Code Agent 默认在临时 workspace/worktree 工作，限制网络、进程、文件系统和资源。

凭证使用短期、任务范围身份；读源码不自动获得云、生产数据库和发布权限。

常见权限阶梯：

```text
只读分析 → 工作区 patch → 本地验证 → 创建 PR
→ 预览环境 → 受审发布 → 生产写入
```

每级需要更强证据和批准。高风险动作采用双人或领域 owner 确认，批准应绑定精确 diff、参数和版本，不能批准模糊意图后允许替换内容。

## 9. 生成代码的 provenance

变更应记录：任务、基线 commit、模型/agent/version、加载的 Rule/Skill、工具调用、diff、验证结果和人类批准。

不必把全部 Prompt 或秘密写进日志。保留能复现决策的最小元数据，并按隐私和商业敏感度控制访问。

生成代码使用的依赖、片段和许可证仍要走供应链审查。AI 提议包名时先验证官方来源、维护状态和是否真实存在。

Git author / committer 应按仓库签名、DCO 或贡献政策如实记录；交付责任由明确的 PR owner、领域 owner 或批准记录承担。“AI 写的”不是事故免责理由。

## 10. Pre-PR 质量闭环

建议在创建 PR 前执行：

1. 检查 diff 是否超出任务边界；
2. 运行 formatter/type/lint/dependency policy 及受影响测试；
3. 检查秘密、漏洞、许可证和生成依赖；
4. 对照 Rule/ADR/接口审查，展示未验证假设和失败命令；
5. 生成变更与风险说明，高风险任务运行专用 eval；
6. 人类 review 业务语义和架构取舍。

确定性 validator 优先于 LLM critic。LLM 适合开放语义审查，但需要 rubric、校准和误报治理。

## 11. Eval 要评任务与轨迹

数据集来源：真实失败脱敏、迁移案例、专家边界、合成变体和红队。

评估维度：

- 任务是否完成且未扩 scope，是否保持 API/领域/模块不变量；
- 测试、构建和运行结果；
- 工具选择、参数、重复和批准；
- 安全、隐私、依赖和许可证；
- diff 大小、可读性和维护成本；
- 人类返工、生产逃逸、延迟及模型/工具/基础设施成本。

按任务类型、仓库、风险、新旧模块和团队切片；总平均会掩盖高风险失败。

## 12. 人机职责分配

AI 擅长穷举、机械迁移、搜索调用链、生成候选和执行反馈循环。

人负责：问题是否值得做、业务语义、质量属性取舍、权限授予、未知风险、异常处置和发布责任。

审查资源会成为新瓶颈。减少无价值 diff、提升预验证和风险分流，比让 AI 生成更多代码更重要。

高风险领域可以要求设计先行、双人 review、shadow 和更小自主范围；低风险文档/机械修复可提高自治。

## 13. 平台与组织视角

平台团队适合提供：Context API、Rule/Skill registry、MCP/tool gateway、沙箱、模型路由、预算、eval runner、审计和 PR 集成。

领域团队拥有业务 Rule、Skill 样例、关键 eval、review 和事故；安全团队维护权限与红队；法务处理数据/许可证边界。

模型供应商可替换性来自内部 contract、eval 和证据，不是同时接十个模型。升级前对固定任务集和 canary 比较质量、风险、成本与延迟。

## 14. 常见失败模式

- 把整个 monorepo 塞进 Prompt，成本高且边界混乱；
- 未经团队对齐就让 AI 生成 Rule；
- Agent 读取 home、Token 或生产配置；
- MCP 工具相信模型提交的 user/tenant；
- 测试绿色就自动合并，需求和权限无人审；
- LLM critic 互相认同，确定性错误仍漏过；
- 生成新依赖不查来源，遭遇幻觉包或供应链风险；
- 用接受率和代码行数证明 ROI；
- Prompt/Skill/model 升级没有版本和 eval；
- 人类只做橡皮图章，责任边界消失。

## 15. 反花架子门槛

扩大 Code Agent 前至少证明：仓库边界清楚、命令可重复、工具最小权限、敏感目录有政策、Pre-PR 可验证、关键任务有 eval、变更有 owner 和回退。

一个 pilot 要比较同类任务的前置时间、返工、缺陷、review 负担和成本，而非 demo 速度。

若 AI 产量上升但 PR 更大、返工更多、事故更多或资深 review 被淹没，应缩小自治范围并修工程环境。

## 16. 建议指标

- 同类任务从理解到生产的前置时间；
- 首次验证通过率与人类返工时间；
- 逃逸缺陷、安全违规和越权动作；
- AI diff 大小、scope 扩张和回滚率；
- review 排队与高风险发现；
- Rule/Skill 命中、过期、冲突和失败率；
- Context 新鲜度、相关性、敏感数据拒绝；
- eval pass@1、方差、关键 slice 与误报；
- 每个成功任务的模型/工具/runner 成本；
- 手工接管、取消和平台绕过。

指标评系统和工作流，不按个人“AI 使用率”排名。

## 17. 架构评审清单

- 任务是否适合 AI，自主级别与风险匹配吗？
- 仓库边界和权威命令是否对人也清楚？
- Context 是否最小、新鲜、可追溯并按 ACL 过滤？
- Rule 是否来自团队共识且能自动验证？
- Skill 是否由真实路径提炼并有停止/恢复？
- Tool/MCP 是否在执行端授权、幂等和审计？
- 沙箱、网络、秘密和资源是否最小权限？
- 批准是否绑定具体 diff、工具和参数？
- Pre-PR 是否先运行确定性验证？
- eval 是否覆盖结果、轨迹、高风险 slice 和成本？
- 人类最终负责什么，事故时谁接管？
- 模型/Prompt/Rule/Skill 升级如何 canary 与回退？

## 官方延伸阅读

- [美团技术团队：用 Agent 评测思路管理 AI Coding](https://tech.meituan.com/2026/05/07/Agent-AI-Coding.html)
- [腾讯 CloudBase AI Toolkit](https://github.com/TencentCloudBase/CloudBase-AI-Toolkit)
- [字节跳动 Web Infra](https://github.com/web-infra-dev)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/specification/)
- [中国信通院：智能化软件开发落地实践指南](https://www.caict.ac.cn/kxyj/qwfb/ztbg/202409/P020240919585073158926.pdf)

## 现有 Master 交叉链接

- AI 辅助开发的验证责任：[JavaScript 与浏览器第 16 章](../《JavaScript%20与浏览器高级学习问题》/16-调试测试可观测与可靠交付/00-讲义.md)
- TS 迁移与 AI 协作：[TS Master 第 17 章](../TS%20Master/17-迁移升级TS6到TS7与AI协作/00-讲义.md)
- Agent 工具与外部系统：[AI Agent Master 第 09 章](../AI%20Agent%20Master/09-工具工程与外部系统集成/00-讲义.md)
- MCP 与工具生态：[AI Agent Master 第 14 章](../AI%20Agent%20Master/14-MCP协议与工具生态/00-讲义.md)
- Eval 质量闭环：[AI Agent Master 第 17 章](../AI%20Agent%20Master/17-Evals测试与质量闭环/00-讲义.md)
- Agent 安全与沙箱：[AI Agent Master 第 19 章](../AI%20Agent%20Master/19-Agent安全隐私与沙箱/00-讲义.md)
- Code Agent 与环境反馈：[AI Agent Master 第 21 章](../AI%20Agent%20Master/21-浏览器代码研究与多模态Agent/00-讲义.md)

## 本章结论

AI-native 研发不是让模型写更多代码，而是把上下文、约束、工具、沙箱、证据和人类责任设计成一条可治理生产线。AI 放大执行力，人仍负责判断什么重要以及是否可以上线。
