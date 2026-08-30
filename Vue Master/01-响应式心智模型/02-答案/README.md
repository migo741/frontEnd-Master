# 答案与复盘

## 题 1 核心实现

```ts
type Job = (() => void) & { deps?: Set<Job>[]; scheduler?: () => void }
const bucket = new WeakMap<object, Map<PropertyKey, Set<Job>>>()
let active: Job | undefined

function cleanup(job: Job) {
  job.deps?.forEach(dep => dep.delete(job))
  job.deps = []
}

export function effect(fn: () => void, scheduler?: () => void) {
  const job: Job = () => {
    cleanup(job)
    active = job
    try { fn() } finally { active = undefined }
  }
  job.scheduler = scheduler
  job.deps = []
  job()
  return job
}

function track(target: object, key: PropertyKey) {
  if (!active) return
  let depsMap = bucket.get(target)
  if (!depsMap) bucket.set(target, depsMap = new Map())
  let dep = depsMap.get(key)
  if (!dep) depsMap.set(key, dep = new Set())
  if (!dep.has(active)) { dep.add(active); active.deps!.push(dep) }
}

function trigger(target: object, key: PropertyKey) {
  const effects = new Set(bucket.get(target)?.get(key) ?? [])
  effects.forEach(job => job.scheduler ? job.scheduler() : job())
}

export function reactive<T extends object>(raw: T): T {
  return new Proxy(raw, {
    get(target, key, receiver) {
      track(target, key)
      return Reflect.get(target, key, receiver)
    },
    set(target, key, value, receiver) {
      const old = Reflect.get(target, key, receiver)
      const ok = Reflect.set(target, key, value, receiver)
      if (!Object.is(old, value)) trigger(target, key)
      return ok
    }
  })
}
```

computed 的关键不是再包一层 effect，而是 scheduler 只把 `dirty = true` 并触发 computed 自己的订阅者；getter 在 dirty 时才执行内部 runner。优秀答案还会发现嵌套 effect 需要 effect stack，上述最小实现只有单层 active，是刻意留下的边界。

## 题 2 参考方案

```ts
let requestVersion = 0

watch(keyword, async value => {
  const version = ++requestVersion
  const controller = new AbortController()
  onWatcherCleanup(() => controller.abort())
  loading.value = true
  try {
    const data = await api.search(value, { signal: controller.signal })
    if (version === requestVersion) list.value = data
  } catch (error) {
    if (!(error instanceof DOMException && error.name === 'AbortError')) throw error
  } finally {
    if (version === requestVersion) loading.value = false
  }
}, { immediate: true })
```

AbortController 节省资源，version 防御不支持 abort 或已越过取消点的实现。debounce 只减少发起次数，不能证明前一请求已取消，也不能解决卸载清理。复写后再补测：第二个请求失败、首个请求晚成功时，页面必须显示第二个请求的错误而不是旧数据。

