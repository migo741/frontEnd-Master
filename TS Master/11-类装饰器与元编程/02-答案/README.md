# 第 11 章参考答案

## 练习一

Token 用闭包/unique symbol 关联：

```ts
declare const tokenType: unique symbol
type Token<T> = Readonly<{key: symbol; description: string; [tokenType]?: (value: T) => T}>

function token<T>(description: string): Token<T> {
  return {key: Symbol(description), description}
}
```

phantom 函数位置让 T 保持较严格关联；runtime 用 key。Provider tuple：

```ts
type Values<T extends readonly Token<unknown>[]> = {[K in keyof T]: T[K] extends Token<infer U> ? U : never}
type FactoryProvider<T, D extends readonly Token<unknown>[]> = {
  token: Token<T>; deps: D; useFactory: (...deps: Values<D>) => T | Promise<T>; scope: Scope
}
```

异构注册表内部需局部 erased provider/unknown adapter，公共注册时建立不变量。build 做 DFS 三色检测并给 token path。request scope cache 绑定显式 RequestContainer，绝不模块全局；dispose 逆依赖/创建顺序并聚合错误。

## 练习二

legacy 依赖：参数 decorator、新旧调用签名、descriptor、emitDecoratorMetadata 的 design:type/paramtypes、Reflect API、执行顺序。标准 decorator 不自动兼容这些，且 interface/generic 本来也无法反射。库若框架消费者强依赖 legacy，暂时维持并隔离可能比半迁移安全。

标准 trace：

```ts
function trace<This, Args extends unknown[], R>(
  original: (this: This, ...args: Args) => R,
  context: ClassMethodDecoratorContext<This, (this: This, ...args: Args) => R>,
) {
  return function(this: This, ...args: Args): R {
    const span = startSpan(String(context.name))
    try {
      const result = original.apply(this, args)
      if (result instanceof Promise) {
        return result.finally(() => span.end()) as R
      }
      span.end(); return result
    } catch (error) {
      span.recordException(error); span.end(); throw error
    }
  }
}
```

Promise-like 跨 realm/thenable 可进一步使用检测或 `Promise.resolve`，但会改变返回 identity/类型；明确支持范围。显式 route 定义携带 runtime Schema，类型从 schema infer，比 design:paramtypes 的粗类型安全。

