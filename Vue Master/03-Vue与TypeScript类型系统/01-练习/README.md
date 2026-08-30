# 练习：把非法状态赶出组件

## 题 1（45 分钟）

重构以下状态，不允许 boolean 组合，不允许模板出现非空断言。要求模板通过穷尽分支得到正确字段类型。

```ts
type State = { loading: boolean; data?: User[]; error?: string }
```

加入“刷新时保留旧数据”的业务后，模型仍要准确。

## 题 2（60 分钟）

为通用 `DataTable<T>` 设计类型：`rows`、`rowKey`、列定义、`cell` 插槽、`select` 事件。列的 `key` 必须是 `T` 的键；format 函数应得到对应字段类型。先写使用侧的理想代码，再反推组件类型。禁止 `Record<string, any>`。

