# 第 10 章参考答案

## 练习一

协议核心：

```ts
interface Schema<T> {
  safeParse(value: unknown):
    | {success: true; data: T}
    | {success: false; issues: readonly Issue[]}
}

type ClientError =
  | {kind: 'network'; cause: unknown}
  | {kind: 'aborted'; reason?: unknown}
  | {kind: 'http'; status: number; requestId?: string; body?: unknown}
  | {kind: 'decode'; status: number; issues: readonly Issue[]; requestId?: string}
```

```ts
async function get<T>(url: string, schema: Schema<T>, signal?: AbortSignal): Promise<Result<T, ClientError>> {
  try {
    const response = await fetch(url, {signal})
    const requestId = response.headers.get('x-request-id') ?? undefined
    if (!response.ok) return err(await parseHttpError(response, requestId))
    const raw: unknown = response.status === 204 ? null : await boundedJson(response)
    const parsed = schema.safeParse(raw)
    return parsed.success ? ok(parsed.data) : err({kind:'decode', status:response.status, issues:parsed.issues, requestId})
  } catch (cause) {
    return signal?.aborted ? err({kind:'aborted', reason:signal.reason}) : err({kind:'network', cause})
  }
}
```

超时可 `AbortSignal.timeout`/`AbortSignal.any`（按目标 runtime 支持）或自建 controller 监听外部 signal，finally 清 timer/remove listener。路径模板类型可辅助，但运行时必须检查替换后无 `:param`。

## 练习二

管线：先 parse minimal envelope → 按 version 选 schema → `migrateV1toV2` → `migrateV2toV3` → `parseV3Domain`。每步纯函数返回 Result，并记录 migration id/原记录 key/hash，不记录敏感 raw。

不要把 migration 直接原地覆盖唯一副本：事务内写新 store/新字段，校验成功再标记，支持断点；失败放 quarantine 带安全错误。future version 保留原 bytes/元数据，当前客户端只读/提示升级。

100k 条 cursor 分批（如 100–1000，按测量），每批让出/提交事务，AbortSignal 在批间检查；进度由 processed/failed/total estimate。迁移器必须 deterministic，重复输入得到同输出；若需 clock/id 由记录/注入提供。

删除 v1 migration 前看生产/遥测与备份的 v1 数量为零超过保留窗口，发布说明/回滚版本不再需要；否则旧客户端或长期离线设备会失去数据。

