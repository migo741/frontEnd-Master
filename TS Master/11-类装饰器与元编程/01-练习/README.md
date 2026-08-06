# 第 11 章练习

## 练习一：类型安全插件容器

插件提供 token、依赖和 factory：

```ts
const LoggerToken: Token<Logger>
const UserRepoToken: Token<UserRepo>
```

要求：

- `Token<T>` 运行时唯一且保留 T；错误 token 无法 resolve 成别的类型。
- provider 支持 value/factory/class；factory 依赖 tuple 精确推断。
- build 时检测缺失依赖和循环（运行时）；错误路径可读。
- 容器 scope：singleton/request/transient；request 不跨用户泄漏。
- 不靠 interface runtime reflection；不使用全局 mutable registry。
- 测试两个同名 token 不冲突、循环、scope、dispose 顺序。

## 练习二：legacy→标准装饰器审计（高难）

旧 Nest-like 库使用 `experimentalDecorators + emitDecoratorMetadata + reflect-metadata`，有类/方法/参数装饰器。

任务：

- 列出不能直接迁移到标准 decorator 的点，特别是参数与 design:type metadata。
- 写一个保持 this/args/return 的标准 `@trace` 方法装饰器，覆盖 sync/async/throw。
- 设计显式 `defineRoute({input,output,handler})` 替代参数反射。
- 给双轨发布/编译策略，避免消费者配置被库绑死。
- 检查 decorator side effects、tree-shaking、声明文件和测试。

可选择暂不迁移，但必须给升级条件和风险缓解。

