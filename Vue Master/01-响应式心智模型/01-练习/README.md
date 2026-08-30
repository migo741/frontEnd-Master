# 练习：最小响应式内核与竞态修复

## 题 1（60 分钟）

实现 `reactive`、`effect` 和 `computed` 的最小版本，必须通过这些场景：动态分支依赖会清理；同一 effect 不重复订阅；连续写入可由 scheduler 合并；computed 懒执行且依赖改变后只标脏，读取时重算。

限制：不参考 Vue 源码，不处理数组和 Map；写出至少 6 个断言。一级提示：effect 每次执行前需要从旧 dependency sets 中删除自己。

## 题 2（30 分钟）

下面搜索框在慢网下会显示旧结果，组件卸载后也可能写状态。给出最小修改，并说明为什么仅 debounce 不够。

```ts
watch(keyword, async value => {
  loading.value = true
  list.value = await api.search(value)
  loading.value = false
}, { immediate: true })
```

验收：快速输入 `v`、`vu`、`vue` 时只能提交最后一个结果；abort 不显示错误；最后一次请求结束前 `loading` 不得被旧请求改为 false。

