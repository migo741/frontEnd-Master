# 第 15 章参考答案

## 练习一

endpoint definition 保留 Schema 值，并通过 Schema 的 output brand 推断类型；client 唯一 runtime pipeline 是 serialize input → fetch → parse unknown → Result。业务错误与协议错误分开，避免服务器返回坏数据却伪装成正常业务失败。

React hook 每次 effect 创建 controller，cleanup abort；用稳定 query key/sequence 防止不合作请求回写。Vue 使用 `watch` 的 cleanup/`onScopeDispose`，getter 输入先规范化，返回 readonly refs。两 adapter 共享 cache 时，cache 存已验证领域值，不存框架 ref/state。

类型测试覆盖 endpoint 输入缺字段、路径参数错类型、成功值推断、error 判别穷尽、adapter input 推断。runtime 覆盖 Schema 拒绝、abort、race、cache key、error mapping。Node adapter 不假设浏览器 globals；credentials/cookie 通过 transport interface 注入。

## 练习二

先组合轴，而不是做一个几十字段 interface：

```ts
type Mode<T> =
  | {multiple?: false; value: T | null; onChange(v: T | null): void}
  | {multiple: true; value: readonly T[]; onChange(v: readonly T[]): void}

type Control<T> =
  | {value: T; defaultValue?: never}
  | {value?: never; defaultValue?: T}

type Common<T> = {
  items: readonly T[]
  getKey: (item: T) => string
  renderItem: (item: T, state: ItemState) => ReactNode
}
```

真实实现需调整 Control 与 Mode 的 value 形状，可分 single/multiple 两个命名 props 以获得更短报错。对象 item 要求显式 getKey；字符串可提供 identity 默认。change 回调返回语义值，不泄漏 DOM event。

类型测试验证 items 推断 callback T、模式与 value 配对、controlled/uncontrolled 互斥、错误 key 返回。e2e 覆盖方向键、Home/End、Enter/Escape、typeahead、焦点恢复、ARIA active descendant、disabled item、屏幕阅读器名称，以及虚拟列表滚动后 active item 的 DOM/ARIA 一致性。这些都不能由类型系统证明。
