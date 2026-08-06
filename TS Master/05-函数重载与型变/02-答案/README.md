# 第 05 章参考答案

## 练习一

```ts
type EventMap = Record<PropertyKey, unknown>
type Handler<T> = (payload: T) => void | Promise<void>

class Emitter<E extends EventMap> {
  #listeners = new Map<keyof E, Set<Handler<E[keyof E]>>>()

  on<K extends keyof E>(type: K, handler: Handler<E[K]>): () => void {
    const set = (this.#listeners.get(type) ?? new Set()) as Set<Handler<E[K]>>
    set.add(handler)
    this.#listeners.set(type, set as Set<Handler<E[keyof E]>>)
    let active = true
    return () => {
      if (!active) return
      active = false
      set.delete(handler)
    }
  }

  emit<K extends keyof E>(type: K, payload: E[K]): void {
    const snapshot = [...(this.#listeners.get(type) ?? [])] as Handler<E[K]>[]
    for (const handler of snapshot) {
      Promise.resolve().then(() => handler(payload)).catch(error => this.report(error))
    }
  }

  private report(error: unknown) { /* 注入 telemetry；避免递归 error event */ }
}
```

内部异构 Map 难以在 TS 中保持 key/value 关联，局部断言是封装不变量；公共 API 无 any，测试覆盖。也可为每 key 建独立 closure 避免断言，代价更复杂。emit 遍历快照，新增 listener 下轮生效，取消不影响本轮已捕获；需把语义写文档。

async handler 用显式 Promise.resolve/catch 收集；若事件必须同步完成，类型改为只允许 void 并用 lint 阻止 Promise。

## 练习二

以 decoder 建立返回可信关系：

```ts
interface Decoder<T> { parse(value: unknown): T }

type RequestOptions<T> =
  | {method?: 'GET'; signal?: AbortSignal; decoder: Decoder<T>}
  | {method: 'POST' | 'PUT'; body: unknown; encode(value: unknown): BodyInit; signal?: AbortSignal; decoder: Decoder<T>}

async function request<T>(url: string, options: RequestOptions<T>): Promise<T> {
  const response = await fetch(url, {
    method: options.method ?? 'GET',
    signal: options.signal,
    ...('body' in options ? {body: options.encode(options.body)} : {}),
  })
  if (!response.ok) throw await HttpError.from(response)
  const raw: unknown = response.status === 204 ? null : await response.json()
  return options.decoder.parse(raw)
}
```

若 method 是 union，调用者必须先缩小再构造匹配 options，或数据结构本身使用判别联合。这是正确约束，不应加 any overload。响应 content-type/text 可通过不同 response decoder 封装，而不是在 request 内根据 T 猜运行时。

少量离散便捷调用可 overload，但核心统一接受联合 options；builder 适合大量可选阶段/必须调用顺序，代价是 API/类型更大。本题联合最清晰。

