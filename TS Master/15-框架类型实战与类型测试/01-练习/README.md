# 第 15 章练习

## 练习一：Schema 驱动的跨框架 Query SDK

设计无框架 core：endpoint 同时声明 path、method、input Schema、output Schema 和 error Schema，由此推断 client 调用参数与 Result。再实现：

- React adapter：可取消 query hook，key 与 input 类型关联，旧请求不得覆盖新请求；
- Vue adapter：composable 接受 ref/getter 输入，正确清理 watcher 与请求；
- Node adapter：服务端调用与浏览器 cookie/credential 策略分离。

要求：

- 任意网络响应先以 unknown 解析，不允许 `as Output`。
- core 不 import React/Vue；adapter 不重新声明 DTO。
- 为三层各写至少 4 个类型测试和 4 个 runtime 测试。
- 处理 success、业务错误、协议错误、网络错误和 abort。

## 练习二：Headless Select 公共契约（高难）

分别为 React 和 Vue 3 设计同等能力的 Select：

- item 类型从 items 推断；
- single 模式 `value: T | null`，multiple 模式 `value: readonly T[]`；
- controlled 与 uncontrolled props 互斥；
- `getKey`、`renderItem`、change event 获得精确 T；
- 支持 string item 和 object item；
- 不允许用 object identity 作为唯一持久 key 默认策略。

写正向/负向类型测试，并列出键盘、焦点、ARIA、虚拟滚动必须由 runtime/e2e 覆盖的行为。
