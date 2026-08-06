# 第 18 章参考答案与评分尺

## 练习一：参考架构（不是唯一解）

```text
Browser
├── Router（URL state / loader / boundaries）
├── Query cache（tickets/users/audit）
├── Feature stores（offline queue / AI composer only）
├── Form state（ticket draft）
├── Realtime service（socket + sequence/reconnect）
└── Telemetry adapter
        │ HTTPS / SSE / WS
BFF / Next server
├── Session + tenant/resource authorization
├── Schema + idempotency + rate limit
├── RSC/SSR cache（tenant-safe keys）
├── AI gateway/tool policy/audit
└── Backend APIs / DB / event stream
```

关键不变量：

1. 任意服务端读取/写入同时约束 actor、tenant、resource；前端 guard 只做体验。
2. URL、Query、Form、Feature store 不保存同一真相。
3. 每个异步结果带资源/请求/版本身份；旧结果不能覆盖新意图。
4. 乐观变更按 operation patch 回滚，不恢复全局旧快照。
5. 实时序列缺口先恢复 snapshot；AI tool 未授权/未确认不执行。
6. 日志不含 prompt/token/PII 全文，trace 可跨层关联。

高分项目不会强行同时上 Redux 与 Zustand。若离线队列/AI composer 用 RTK，说明事件日志/中间件收益；若 Zustand，说明 selector/领域 action/持久迁移约束；只用 reducer/context 也可，只要规模证明。

### 评分尺

| 维度 | 0–1 | 2 | 3–4 |
|---|---|---|---|
| 架构 | 库堆砌/双真相 | 边界基本清楚 | 不变量可执行、演进/回滚明确 |
| 正确性 | 只 happy path | 有错误处理 | 竞态/幂等/版本/权限有自动证据 |
| 性能 | “用了 memo” | 有 profile | 基线、根因、收益、预算、真实用户指标 |
| 测试 | 覆盖率截图 | 单元+少量集成 | 风险驱动、可控并发、稳定 E2E/contract |
| 安全/a11y | 未考虑 | 基础规则 | 威胁模型/资源授权/真实键盘辅助技术验收 |
| 运维 | console.log | Error Boundary/日志 | release/trace/SLO/灰度/回滚/事故演练 |
| 表达 | 复述实现 | 能解释选择 | 能量化约束、比较备选、承认未知并设计实验 |

## 练习二：系统设计参考要点

告警数据面与控制面分开。浏览器不接收 10 万行全量每秒变化：服务端按 tenant/权限/筛选建立订阅，snapshot + sequenced deltas；Worker 解码，外部 store 规范化并微批；虚拟列表只订阅可见字段。多人 claim 用服务端版本/lease，UI 乐观但冲突回权威。AI 摘要是异步任务，引用告警 source id，工具操作另行授权确认。

容量示例必须先问输入：若峰值 5,000 events/s、每事件 500B，原始约 2.5MB/s/tenant 前还未算协议；浏览器必须筛选/聚合和背压。延迟目标可能是告警可见 p95<1s、用户 claim 确认<300ms。降级：暂停动画/降低刷新、切摘要计数、禁止实时排序、保留手动刷新；不能丢关键状态转换。

### `useLatestRequest` 参考模型

```tsx
type State<T> =
  | {status: 'idle'}
  | {status: 'loading'; key: string}
  | {status: 'success'; key: string; data: T}
  | {status: 'error'; key: string; error: Error}

function useLatestRequest<T>(key: string | null, fetcher: (key: string, signal: AbortSignal) => Promise<T>) {
  const [attempt, retry] = useReducer(x => x + 1, 0)
  const [state, setState] = useState<State<T>>({status: 'idle'})

  useEffect(() => {
    if (key == null) { setState({status: 'idle'}); return }
    const controller = new AbortController()
    let current = true
    setState({status: 'loading', key})
    fetcher(key, controller.signal).then(
      data => { if (current) setState({status: 'success', key, data}) },
      unknown => {
        if (!current || controller.signal.aborted) return
        setState({status: 'error', key, error: unknown instanceof Error ? unknown : new Error('Unknown')})
      },
    )
    return () => { current = false; controller.abort() }
  }, [key, fetcher, attempt])

  return {state, retry}
}
```

这里要求 fetcher 引用稳定是契约；更成熟 API 可把 fetcher 移模块服务或 Effect Event，但 key 仍是真正依赖。生产用 Query/loader 是因为缓存、去重、预取、重试、失效、SSR 和 DevTools 已被系统解决。

## 18 题的高分关键词

不要背句子，检查是否覆盖：

1. 快照/闭包/updater queue；2. pure render/commit/可中断；3. type+position+key；4. external synchronization/dependency honesty；5. abort + identity；6. 状态分类/团队约束；7. 远端权威/freshness；8. patch/intent/concurrency；9. priority vs fixed time/rate；10. pending vs error fault domain；11. baseline/profile/verify/budget；12. compiler 不修算法/网络；13. 用户行为/HTTP boundary/真实浏览器；14. HTML vs RSC payload/策略取舍；15. 公开端点/资源授权；16. worker+batch+selector+virtualization+backpressure；17. decoder/parser/sequence/buffer/security；18. strangler/adapter/flag/observability/rollback。

## 最终判定

如果你能完成毕业项目并用证据答辩，你具备竞争高级 React 岗位的知识与作品基础。若要达到资深/专家，请继续用真实生产规模验证：带人、跨团队迁移、SLO/事故、成本和长期维护。那部分不能靠一份文稿伪造，但这套训练能让你更快积累正确证据。

