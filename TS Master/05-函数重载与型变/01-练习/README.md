# 第 05 章练习

## 练习一：类型安全 EventEmitter

```ts
type Events = {
  connected: {at: Date}
  message: {id: string; text: string}
  error: {error: Error; retryable: boolean}
}
```

实现：

```ts
on<K extends keyof Events>(type: K, handler: (payload: Events[K]) => void): () => void
emit<K extends keyof Events>(type: K, payload: Events[K]): void
once<K extends keyof Events>(...): () => void
```

要求：

- 错 event/payload/handler 编译失败；unsubscribe 幂等。
- listener 在 emit 中取消/新增不破坏本轮确定语义。
- handler 错误隔离策略明确；async handler 不产生未处理 rejection。
- Events 只读输入；内部不能用业务可见 any。
- 测试参数逆变：只处理特定 message 子型的 handler 为什么不能注册。

## 练习二：API 重载评审（高难）

重构：

```ts
declare function request(url: string): Promise<unknown>
declare function request(url: string, method: 'GET'): Promise<unknown>
declare function request(url: string, method: 'POST', body: object): Promise<unknown>
declare function request<T>(url: string, options: any): Promise<T>
```

任务：

- 消除 any 和“调用者自选 T 即可信”的谎言。
- GET 禁 body；POST/PUT body 需 encoder；响应由 decoder 产生 T。
- 支持 `method: 'GET' | 'POST'` 变量时给合理错误/分支。
- AbortSignal、HTTP 错误、204、JSON/文本响应有明确类型。
- 比较 overload、判别联合 options、builder 三种 API。
- 给 6 个类型负例和运行时 contract 测试。

