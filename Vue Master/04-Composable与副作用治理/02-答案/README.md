# 答案与复盘

## 题 1

```ts
export function useLatestTask<P, R>(runner: (p: P, s: AbortSignal) => Promise<R>) {
  const state = reactive<RemoteData<R>>({ status: 'idle' })
  let version = 0
  let active: AbortController | undefined

  async function run(params: P) {
    active?.abort()
    const mine = ++version
    const controller = active = new AbortController()
    state.status = 'loading'
    try {
      const data = await runner(params, controller.signal)
      if (mine === version && !controller.signal.aborted)
        Object.assign(state, { status: 'success', data, error: undefined })
    } catch (error) {
      if (mine === version && !controller.signal.aborted)
        Object.assign(state, { status: 'error', error })
    }
  }

  function cancel() {
    version++
    active?.abort()
    state.status = 'idle'
  }
  onScopeDispose(cancel)
  return { state: readonly(state), run, cancel }
}
```

参考实现省略了完整 union 的赋值细节，练习时应避免让旧字段残留。关键测试不是“能成功”，而是 A 后发先完成、B 先发后完成时 B 绝不能覆盖 A；取消后 rejected Promise 不产生 error；scope.stop 后也不写状态。

## 题 2

独立版在函数内创建 ref，在 `onMounted` 读取 window 并监听，`onScopeDispose` 移除。它简单隔离，但 N 个组件有 N 个 listener。

单例版应显式创建共享 service：内部用 `effectScope(true)` 管理一个 listener，维护引用计数，首个 consumer attach、最后一个 dispose 时 detach；SSR 时不访问 window，并为每个 SSR 请求创建实例，不能把请求相关状态放进进程全局模块。高级答案应指出：“模块单例”在纯 CSR 可能可用，在 SSR 会跨请求泄漏。

