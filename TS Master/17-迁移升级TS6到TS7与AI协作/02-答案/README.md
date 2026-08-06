# 第 17 章参考答案

## 练习一

第 1 周锁定工具链、统一可复现构建、建立错误/any/suppression/边界基线；第 2 周统一模块协议和环境类型；第 3–4 周先迁支付/价格/订单状态等高风险边界，加 Schema/Result/tests；第 5–6 周按依赖叶节点推进 strict；第 7 周清临时 shim/断言、做发布物 fixtures；第 8 周切 TS 6 主线并保留快速回滚。

前五切面建议：外部订单 API、金额/币种、状态转换、持久化反序列化、公共包出口。它们事故半径大且能形成下游可信核心。每周功能继续，但改到的文件遵循 boy-scout gate，新 any 必须审批。

预算同时看数量和风险权重：边界 any 权重大于测试 mock；裸 ignore 禁增；expect-error 必须 issue/expiry；double assertion 单列。TS 6 车道连续两周稳定、runtime/e2e/tarball fixture 通过再转 blocking。TS 7 进入标准是官方可用预览和关键工具支持，退出标准是诊断/声明/API 无未解释差异、compiler API 工具兼容、性能达到阈值；否则继续 TS 6。

## 练习二

问题至少包括：调用者自选 T；JSON 是 unknown 未验证；没检查 status/content-type；没有错误模型；response body/解析可能失败；无 abort/timeout；泛型与 URL 无关联；DeepSafe 只改静态视图；NonNullable 不能删除 runtime null；数组/函数/Date 都被 object 递归错误处理；可选属性未变 required；递归/大型模型可能拖慢 checker；没有大小限制；没有版本兼容；没有 race/retry/idempotency 策略。

更好的入口由 endpoint 持有 Schema，不让调用者指定 T：

```ts
async function request<S extends Schema>(
  endpoint: {url: string; output: S},
  options: {signal?: AbortSignal}
): Promise<Result<Output<S>, RequestError>>
```

实现先组合 timeout/外部 signal，检查 HTTP 和 content-type，在大小上限内读 body（大响应走 streaming parser），JSON parse 后由 schema safeParse。error union 用 `kind: 'network' | 'aborted' | 'http' | 'protocol' | 'business'` 并保存安全上下文/cause；retry 只对明确幂等且可重试情况。

测试包括恶意/缺字段/null/超大/非 JSON/204/4xx/5xx、超时、用户 abort、慢流、Schema 版本和 race。删除 DeepSafe；如果业务真的要求非空，由 Schema 在 runtime 验证，输出类型从 Schema 推断。对复杂 Schema/类型用 extendedDiagnostics 建预算。
