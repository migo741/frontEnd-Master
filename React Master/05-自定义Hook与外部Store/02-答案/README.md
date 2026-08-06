# 第 05 章参考答案

## 练习一：分层实现

原生 store 是模块级共享资源：

```ts
type NativeStatus = 'online' | 'offline' | 'unknown'

function subscribe(callback: () => void) {
  window.addEventListener('online', callback)
  window.addEventListener('offline', callback)
  return () => {
    window.removeEventListener('online', callback)
    window.removeEventListener('offline', callback)
  }
}

function getSnapshot(): NativeStatus {
  return navigator.onLine ? 'online' : 'offline'
}

function getServerSnapshot(): NativeStatus {
  return 'unknown'
}

export function useNativeOnlineStatus() {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)
}
```

`changedAt` 不能在 `getSnapshot` 每次创建新对象，否则会无限更新。若需要时间，应由真正的 online/offline 事件更新模块缓存：

```ts
let snapshot = {status: 'unknown' as NativeStatus, changedAt: null as number | null}
```

事件发生时仅在 status 改变后创建一个新 snapshot 再通知。

probe 层建议独立为 query/小状态机：native offline 直接 offline；native online 后发轻量健康检查，失败为 degraded，不轻易宣称整个互联网 offline。指数退避加随机抖动，页面 hidden 时 abort；visible 时重试。测试注入 scheduler、clock 和 probe，不能依赖真实网络/时间。

## 练习二：Store 内核

```ts
type Updater<T> = T | ((previous: T) => T)

export function createStore<T>(initial: T) {
  let snapshot = initial
  const listeners = new Set<() => void>()

  return {
    getSnapshot: () => snapshot,
    getServerSnapshot: () => initial,
    setState(updater: Updater<T>) {
      const next = typeof updater === 'function'
        ? (updater as (p: T) => T)(snapshot)
        : updater
      if (Object.is(next, snapshot)) return
      snapshot = next
      for (const listener of [...listeners]) listener()
    },
    subscribe(listener: () => void) {
      listeners.add(listener)
      let active = true
      return () => {
        if (!active) return
        active = false
        listeners.delete(listener)
      }
    },
  }
}
```

基础 Hook：

```tsx
function useStore<T>(store: ReturnType<typeof createStore<T>>): T {
  return useSyncExternalStore(
    store.subscribe,
    store.getSnapshot,
    store.getServerSnapshot,
  )
}
```

带 selector 的严格并发实现不应草率地“订阅后 setSelected”。可使用官方维护的 `use-sync-external-store/with-selector` shim：

```tsx
import {useSyncExternalStoreWithSelector} from 'use-sync-external-store/with-selector'

function useStoreSelector<T, S>(
  store: Store<T>,
  selector: (state: T) => S,
  isEqual: (a: S, b: S) => boolean = Object.is,
) {
  return useSyncExternalStoreWithSelector(
    store.subscribe,
    store.getSnapshot,
    store.getServerSnapshot,
    selector,
    isEqual,
  )
}
```

练习版缺少中间件、DevTools、持久化/迁移、批处理、事务、selector 调试、跨 tab、异步策略、严格类型体验和长期兼容性，因此不能冒充成熟生产库。真正的能力是理解协议后知道何时停止造轮子。

