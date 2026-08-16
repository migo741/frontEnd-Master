# 第 09 章：Web 交付、CDN、资产与第三方治理

> 版本基线：截至 2026-08-16。本章关注发布后浏览器真正拿到什么，以及新旧版本和外部代码如何安全共存。

## 1. 市场与业务问题

前端发布不是“把 dist 上传到 CDN”。
用户可能保留数小时的标签页、离线后恢复、命中不同 CDN 节点，或在旧 App WebView 中加载新 H5。
一个版本还会依赖 HTML、JS chunks、CSS、字体、图片、Source Map、API 和第三方脚本。
任何一层先旧后新、先新后旧，都可能产生只在部分用户上发生的故障。
大型产品还依赖支付、地图、客服、分析、广告和实验 SDK；这些代码处于关键路径，却不由本团队发布。
架构目标是建立可追踪、可兼容、可回滚的交付协议，而不是追求最高 CDN 命中率。

## 2. 本章非目标

- 不讲某家 CDN 控制台或上传命令。
- 不重讲 HTTP header 的基础语法。
- 不把所有第三方脚本一律禁止，也不默认信任知名供应商。
- 不用“一键清缓存”代替版本和兼容设计。

## 3. 制品模型：可变入口与不可变资产

HTML、应用清单和版本指针是可变入口，应快速发现新版本并支持回滚。
带内容 hash 的 JS、CSS、字体和图片是不可变资产，可长期缓存。
相同 URL 的内容永远不覆盖，这是缓存正确性的第一条不变量。
一次构建产生唯一 release id、资产清单、依赖图和完整性信息。
HTML 只引用该 release 已确认上传成功的资产。
发布顺序通常是先上传不可变资产，再发布入口，最后渐进放量。
回滚只移动入口或流量指针，不删除刚发布资产。

## 4. HTML 与 JS 多版本兼容

用户打开 v41 HTML 后，可能在 v43 发布后才点击一个懒加载路由。
如果 v41 chunk 已删除，用户会遇到 `ChunkLoadError`。
如果 v41 JS 调用只接受 v43 客户端的新 API，也会在长会话中失败。
因此生产系统必须明确兼容窗口，而不是只保留“当前版本”。
建议至少保留覆盖最大会话时长、回滚窗口和 CDN 传播延迟的若干 release 资产。
API 使用向后兼容的扩展—迁移—删除流程，旧客户端流量归零后再删旧字段。
协议不兼容时使用显式版本或 capability negotiation，不靠 User-Agent 猜测。
前端请求携带 release id，服务端和日志才能识别版本偏差。

## 5. 更新提示与自恢复

检测到 chunk 缺失时可以提示刷新，但刷新必须有上限并保留用户未提交状态。
不能在错误处理器中无限 `location.reload()`，这会制造刷新风暴。
新的 release 可通过轻量 manifest 检查发现，不要求每个请求都 no-cache。
关键写操作前若发现客户端过旧，可先保存草稿，再要求升级。
Service Worker 更新需要 install、activate、client claim 和旧 tab 的明确策略。
不能让新 SW 立即接管却返回与旧 JS 不兼容的响应。
自恢复路径本身要有指标和故障注入测试。

## 6. CDN 参考路径

浏览器请求先经过 DNS、边缘节点、可能的区域层、源站盾和对象存储或应用源站。
每层都可能改变 cache key、压缩、header、错误缓存和日志采样。
架构文档应画出真实请求路径，而不是只画一个“CDN”方框。
静态资产通常按 path + encoding 变体缓存。
HTML 可能还受 host、locale、设备或实验影响；维度越多，命中率和误配风险越高。
未经审查的 query 参数进入 key 会被攻击者制造缓存碎片。
忽略关键 `Vary` 又会把不同响应串给用户。

## 7. 缓存策略按对象分类

**Hashed asset**：长 TTL、immutable、可跨 release 复用。
**HTML / manifest**：短 TTL 或 revalidate，支持 stale-if-error 与明确回滚。
**公开 API**：按业务版本和 locale 分区，允许受控陈旧。
**个性化 API**：默认 private/no-store，除非身份维度和隔离已证明。
**错误响应**：只对明确安全的 404/410 短暂负缓存，避免把临时 5xx 固化。
**Source Map**：不公开索引，上传到受控错误平台并限制访问。
每类对象都要写 owner、TTL、purge、保留和容量预算。

## 8. 压缩、协商与资产预算

Brotli/Gzip 变体必须进入正确 cache key，并保持 Content-Encoding 一致。
图片格式协商不能无限增加变体；优先由构建或图片服务管理。
字体子集能减少字节，但缺字回退和版权要验证。
预加载只给真正关键且稳定的资源，错误 preload 会争抢主内容带宽。
HTTP/2/3 不会消除过多请求、错误优先级或第三方连接成本。
资产预算应按 route 和设备定义，而不是只约束仓库总 bundle。

## 9. CDN 失效与回源保护

Purge 是运营工具，不是正确性协议。
全网失效存在传播时间、失败和供应商差异。
不可变 URL 让正确性不依赖 purge 成功。
热点入口过期时使用 request collapsing 或 origin shield，避免所有边缘同时回源。
源站需要独立限流、隔舱和容量保护，不能假设 CDN 永不绕过。
CDN 故障时可切备用域名或回源，但 DNS TTL、证书和缓存预热要事先演练。
stale-if-error 只适合允许陈旧的公开响应，不能用于授权决策。

## 10. 第三方脚本先做资产清册

每个第三方必须记录：业务目的、owner、供应商、加载页面、数据字段、权限、SLO、合同期限和 kill switch。

没有 owner 的脚本默认不能进入生产。

“分析需要”不是无限采集的理由，要列出具体事件和保留期限。

重复分析 SDK 会放大 CPU、网络、隐私和事件不一致成本。

供应商更新策略必须明确：固定版本、受控升级，还是远程可变脚本。

远程可变脚本等同供应商拥有生产代码发布权，应按高风险依赖管理。

## 11. 第三方隔离层级

最低风险是服务端调用，浏览器不直接执行供应商代码。

需要 UI 时可使用受限 iframe，结合 sandbox、allow 和消息 Schema。

必须同页执行时，采用 CSP、Trusted Types、最小数据、延迟加载和超时/降级。

Subresource Integrity 适合内容固定的跨域静态资源，但不适合内容频繁变化的 loader。

代理第三方脚本可以获得缓存与审查能力，也意味着团队承担更新和许可责任。

高风险支付或身份组件要遵循供应商官方集成边界，不能为了复用任意改写。

第三方失败不能阻塞主导航、登录或结算核心路径。

## 12. 同意、隐私与数据边界

在适用法律、地区政策或产品承诺要求取得同意的场景，非必要追踪在有效同意前不得加载或写标识符；具体分类与合法基础由隐私、法务和产品共同确认。

撤回同意后要停止后续发送，并按政策处理已有标识。

事件 payload 采用 allowlist，不把 DOM、URL 查询、表单或聊天正文整体转发。

地区、年龄、租户和企业合约可能改变允许的数据范围。

前端埋点 Schema 与服务端接收规则共同校验，不能只靠 SDK 约定。

数据流图要覆盖供应商的子处理方和跨境位置。

隐私检查与性能预算进入第三方接入门禁，而非上线后的补充表单。

## 13. 供应链与运行时完整性

构建时依赖治理和运行时第三方治理是两条不同链路。

前者关注 lockfile、来源、构建和制品证明；后者关注浏览器实际下载的远程代码。

制品清单应能把 release 追溯到源提交、构建环境和依赖版本。

HTML 安全 header 作为发布产物验证，不能只存在网关 Wiki。

CSP report-only 可用于迁移观测，但长期不阻断就不是安全边界。

发现供应商被入侵时，要能按配置或边缘规则关闭，而不等待完整业务发版。

## 14. 失败模式与反花架子门槛

- 覆盖同一 hashed URL 的内容，导致节点返回不同字节。
- 发布入口早于资产，全球部分节点短时白屏。
- 每次发版删除旧 chunks，长会话懒加载失败。
- 只测试最新版前后端，不测试旧 HTML/JS 对新 API。
- 用 purge 修所有问题，却没有传播与失败观测。
- 个性化 HTML 被 CDN 公共缓存，造成跨用户泄漏。
- Service Worker 缓存策略无人所有，形成“僵尸版本”。
- 第三方同步脚本位于 head，供应商延迟拖慢核心任务。
- CSP 允许 `unsafe-inline` 和任意域，却被当作安全成果。
- 资产平台只追求命中率，不跟踪错误命中和回源风暴。

反花架子门槛：没有 release manifest、兼容窗口、回滚演练和第三方 owner，就不批准“全球加速平台”提案。

## 15. 平台与组织视角

交付平台拥有制品规范、上传顺序、签名、CDN 策略、版本可视化和回滚控制面。

业务团队拥有 route 预算、第三方业务价值、兼容声明和用户降级体验。

安全与隐私团队提供机器可执行政策和高风险例外流程。

SRE 负责源站容量、CDN 故障切换和跨供应商演练。

采购终止供应商合同时必须触发技术下线任务，避免合同结束但脚本仍运行。

平台应提供 Golden Path 和逃生口，而不是让每个团队复制 CDN 配置。

## 16. 指标

- 按 release/地区/运营商的 HTML、asset、API 成功率与尾延迟。
- asset 404、ChunkLoadError、完整性失败和自动恢复成功率。
- 新旧 release 并存分布、最长活跃会话和兼容流量。
- CDN 命中率、错误命中率、回源率、purge 延迟和 origin shield 效果。
- 每 route JS/CSS/字体/图片字节与主线程时间。
- 第三方字节、请求、CPU 长任务、错误和核心旅程影响。
- 无 owner/过期第三方数量、kill switch 演练时间。
- CSP/Trusted Types 违规、同意前请求和数据策略违规。
- CDN/源站成本与每千次核心任务成本。

## 17. 架构评审清单

- 哪些入口可变，哪些资产不可变？
- 发布顺序是否保证 HTML 只引用已存在资产？
- 旧 HTML/JS、懒加载 chunk 和新 API 的兼容窗口多长？
- release id 能否贯穿浏览器、CDN、API 和日志？
- cache key 是否包含必要维度且没有无界碎片？
- 哪些响应可 stale，哪些必须 fail closed？
- Service Worker 如何升级、回滚和清除旧缓存？
- CDN 绕过、回源风暴和供应商区域故障如何保护？
- 每个第三方的 owner、数据、性能预算和 kill switch 是什么？
- CSP、SRI、iframe 或服务端代理为何适合当前脚本？
- 是否演练旧 tab、灰度、回滚和第三方超时组合？
- 哪组指标会阻止继续放量？

## 官方延伸阅读

- [RFC 9111：HTTP Caching](https://www.rfc-editor.org/rfc/rfc9111)
- [MDN Cache-Control](https://developer.mozilla.org/docs/Web/HTTP/Reference/Headers/Cache-Control)
- [W3C Content Security Policy Level 3](https://www.w3.org/TR/CSP3/)
- [W3C Subresource Integrity](https://www.w3.org/TR/SRI/)
- [web.dev：加载第三方 JavaScript](https://web.dev/articles/efficiently-load-third-party-javascript)
- [OWASP Third Party JavaScript Management](https://cheatsheetseries.owasp.org/cheatsheets/Third_Party_Javascript_Management_Cheat_Sheet.html)

## 现有 Master 交叉链接

- [JS 与浏览器第 07 章：ESM、包边界与构建语义](../《JavaScript%20与浏览器高级学习问题》/07-ESM包边界与构建语义/00-讲义.md)
- [JS 与浏览器第 11 章：Fetch、缓存、流与实时通信](../《JavaScript%20与浏览器高级学习问题》/11-Fetch缓存流与实时通信/00-讲义.md)
- [JS 与浏览器第 14 章：Web 安全与前端信任边界](../《JavaScript%20与浏览器高级学习问题》/14-Web安全与前端信任边界/00-讲义.md)
- [JS 与浏览器第 16 章：调试、测试与可靠交付](../《JavaScript%20与浏览器高级学习问题》/16-调试测试可观测与可靠交付/00-讲义.md)
- [Backend Master 第 02 章：代理与 HTTP 语义](../Backend%20Master/02-网络反向代理与HTTP语义/00-讲义.md)
- [Backend Master 第 07 章：Schema 演进、迁移与恢复](../Backend%20Master/07-Schema演进迁移与恢复/00-讲义.md)
- [Backend Master 第 21 章：CI/CD、云发布与灾难恢复](../Backend%20Master/21-容器CI-CD云发布与灾难恢复/00-讲义.md)

## 本章结论

可靠 Web 交付依赖不可变资产、可变入口、明确兼容窗口和可回滚控制面。

HTML、新旧 JavaScript、API 与第三方代码长期并存，不是发布异常而是正常生产状态。

CDN 的最高价值不是“快”，而是在不牺牲正确性、安全和恢复能力的前提下稳定交付。
