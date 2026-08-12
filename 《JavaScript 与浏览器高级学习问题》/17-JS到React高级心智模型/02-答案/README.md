# 第 17 章参考答案

## 练习一

建议所有权：组件 ref 持有 Canvas DOM；一个 Effect 会话持有 Worker/observer/listeners/RAF；React state 只保存要驱动 JSX 的可见状态；高频 pointer 坐标可先留在外部会话，在一帧一次的边界提交。

React 19.2 可用 `useEffectEvent` 让由 Effect 安装的原生事件读取最新 props，同时不为回调身份变化重建 Worker。下面代码把 Worker 句柄真正接入数据 Effect，也覆盖拖动、键盘、DPR 与 ARIA：

```jsx
function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

function indexAtPointer(canvas, event, length) {
  if (length === 0) return -1
  const rect = canvas.getBoundingClientRect()
  const ratio = clamp((event.clientX - rect.left) / Math.max(1, rect.width), 0, 1)
  return Math.min(length - 1, Math.floor(ratio * length))
}

function drawWaveform(canvas, values, cursor) {
  const rect = canvas.getBoundingClientRect()
  const dpr = globalThis.devicePixelRatio || 1
  const width = Math.max(1, Math.round(rect.width * dpr))
  const height = Math.max(1, Math.round(rect.height * dpr))
  if (canvas.width !== width) canvas.width = width
  if (canvas.height !== height) canvas.height = height

  const context = canvas.getContext('2d')
  context.setTransform(dpr, 0, 0, dpr, 0, 0)
  context.clearRect(0, 0, rect.width, rect.height)
  context.beginPath()
  values.forEach((value, index) => {
    const x = values.length < 2 ? 0 : index * rect.width / (values.length - 1)
    const y = rect.height / 2 - value * rect.height / 2
    if (index === 0) context.moveTo(x, y)
    else context.lineTo(x, y)
  })
  context.stroke()
  if (values.length) {
    const x = values.length < 2 ? 0 : cursor * rect.width / (values.length - 1)
    context.fillRect(x - 1, 0, 2, rect.height)
  }
}

function Waveform({samples, onSelect}) {
  const canvasRef = useRef(null)
  const workerRef = useRef(null)
  const generationRef = useRef(0)
  const modelRef = useRef([])
  const cursorRef = useRef(0)
  const [cursor, setCursor] = useState(0)

  const selectIndex = useEffectEvent(index => {
    if (samples.length === 0) return
    const next = clamp(index, 0, samples.length - 1)
    cursorRef.current = next
    setCursor(next)
    onSelect(samples[next].id)
  })

  useEffect(() => {
    const canvas = canvasRef.current
    const worker = new Worker(new URL('./wave.worker.js', import.meta.url), {type: 'module'})
    const controller = new AbortController()
    workerRef.current = worker
    let frame = 0
    let disposed = false
    let dragging = false
    let dprQuery = null

    const scheduleDraw = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        if (!disposed) drawWaveform(canvas, modelRef.current, cursorRef.current)
      })
    }

    const onDprChange = () => {
      watchDpr()
      scheduleDraw()
    }
    function watchDpr() {
      dprQuery?.removeEventListener('change', onDprChange)
      dprQuery = matchMedia(`(resolution: ${globalThis.devicePixelRatio || 1}dppx)`)
      dprQuery.addEventListener('change', onDprChange, {once: true})
    }

    const chooseFromPointer = event => {
      const index = indexAtPointer(canvas, event, modelRef.current.length)
      if (index >= 0) selectIndex(index)
      scheduleDraw()
    }
    const onPointerDown = event => {
      dragging = true
      canvas.setPointerCapture(event.pointerId)
      chooseFromPointer(event)
    }
    const onPointerMove = event => {
      if (dragging) chooseFromPointer(event)
    }
    const onPointerEnd = event => {
      dragging = false
      if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId)
    }
    const onKeyDown = event => {
      const last = modelRef.current.length - 1
      if (last < 0) return
      const next = {
        ArrowLeft: cursorRef.current - 1,
        ArrowDown: cursorRef.current - 1,
        ArrowRight: cursorRef.current + 1,
        ArrowUp: cursorRef.current + 1,
        Home: 0,
        End: last,
      }[event.key]
      if (next === undefined) return
      event.preventDefault()
      selectIndex(next)
      scheduleDraw()
    }

    canvas.addEventListener('pointerdown', onPointerDown, {signal: controller.signal})
    canvas.addEventListener('pointermove', onPointerMove, {signal: controller.signal})
    canvas.addEventListener('pointerup', onPointerEnd, {signal: controller.signal})
    canvas.addEventListener('pointercancel', onPointerEnd, {signal: controller.signal})
    canvas.addEventListener('keydown', onKeyDown, {signal: controller.signal})
    const observer = new ResizeObserver(scheduleDraw)
    observer.observe(canvas)
    watchDpr()

    worker.onmessage = ({data}) => {
      if (disposed || data.type !== 'model' || data.generation !== generationRef.current) return
      modelRef.current = Object.freeze(Array.from(data.values))
      const nextCursor = clamp(cursorRef.current, 0, Math.max(0, modelRef.current.length - 1))
      cursorRef.current = nextCursor
      setCursor(nextCursor)
      scheduleDraw()
    }

    return () => {
      disposed = true
      controller.abort()
      observer.disconnect()
      dprQuery?.removeEventListener('change', onDprChange)
      cancelAnimationFrame(frame)
      worker.terminate()
      if (workerRef.current === worker) workerRef.current = null
    }
  }, [])

  useEffect(() => {
    const worker = workerRef.current
    if (!worker) return
    const generation = ++generationRef.current
    // 不 transfer props 所拥有的 buffer；发送专属于本次消息的 plain data。
    worker.postMessage({
      version: 1,
      type: 'prepare',
      generation,
      values: samples.map(sample => sample.value),
    })
  }, [samples])

  const disabled = samples.length === 0
  return (
    <canvas
      ref={canvasRef}
      tabIndex={0}
      role="slider"
      aria-label="波形时间光标"
      aria-disabled={disabled || undefined}
      aria-valuemin={0}
      aria-valuemax={Math.max(0, samples.length - 1)}
      aria-valuenow={cursor}
      aria-valuetext={disabled ? '没有采样点' : `第 ${cursor + 1} 个采样点`}
    />
  )
}
```

Worker 端的最小协议是收到 `{type:'prepare', generation, values}` 后返回 `{type:'model', generation, values: transformed}`；错误也必须带 generation。真实波形还要把可见数值/时间作为相邻文本或描述提供给屏幕阅读器，不能只有一块 Canvas。

React 18 可用稳定 `selectIndex` + `latestRef` 替代 Effect Event：在 `useLayoutEffect` 中把最新 `samples/onSelect` 写入 ref，原生 listener 调用稳定函数并读取该 ref。不要在 render 里随意改 ref，也不要用 ref 隐藏真正需要重建的资源配置。

测试注入 Worker/observer/RAF/matchMedia 工厂：Strict Mode 额外挂载流程后，每个创建都有一次 terminate/disconnect/cancel；拖动与 Arrow/Home/End 得到相同选择；DPR change 重绘 backing store；手工发送旧 generation 时 model/draw 不变；卸载后迟到消息不 setState。

## 练习二

Store 是 React 外部的状态机，React 只是订阅稳定快照。内部 Map 不得暴露；`Object.freeze(map)` 也阻止不了 `.set()`，所以对外发布冻结的 null-prototype 只读视图。以下示例把 Worker 结果限制为 JSON-like 数据并在边界 clone + deep-freeze：

```js
function deepFreezeJson(value, seen = new WeakSet()) {
  if (value === null || typeof value === 'string' || typeof value === 'boolean') return value
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value !== 'object') throw new TypeError('Worker result must be JSON-like data')
  if (seen.has(value)) throw new TypeError('Worker result cannot be cyclic')
  if (!Array.isArray(value) &&
      Object.getPrototypeOf(value) !== Object.prototype &&
      Object.getPrototypeOf(value) !== null) {
    throw new TypeError('Worker result must be JSON-like data')
  }
  seen.add(value)
  for (const child of Object.values(value)) deepFreezeJson(child, seen)
  seen.delete(value)
  return Object.freeze(value)
}

function immutableResult(value) {
  return deepFreezeJson(structuredClone(value))
}

function encodeQuery(value, seen = new WeakSet()) {
  if (value === null) return ['null']
  if (typeof value === 'string') return ['string', value]
  if (typeof value === 'boolean') return ['boolean', value]
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) throw new TypeError('Query numbers must be finite')
    return ['number', Object.is(value, -0) ? '-0' : String(value)]
  }
  if (typeof value !== 'object') {
    throw new TypeError('Query must contain only finite JSON-like values')
  }
  if (seen.has(value)) throw new TypeError('Query cannot be cyclic')
  seen.add(value)

  let encoded
  if (Array.isArray(value)) {
    // 拒绝稀疏数组、额外属性、accessor；否则 hole/undefined/null 会发生 JSON 碰撞。
    if (Reflect.ownKeys(value).length !== value.length + 1) {
      throw new TypeError('Query arrays must be dense and have no extra properties')
    }
    const items = []
    for (let index = 0; index < value.length; index++) {
      const descriptor = Object.getOwnPropertyDescriptor(value, String(index))
      if (!descriptor || !descriptor.enumerable || !('value' in descriptor)) {
        throw new TypeError('Query arrays must contain enumerable data elements')
      }
      items.push(encodeQuery(descriptor.value, seen))
    }
    encoded = ['array', items]
  } else {
    const prototype = Object.getPrototypeOf(value)
    if (prototype !== Object.prototype && prototype !== null) {
      throw new TypeError('Query objects must be plain records')
    }
    const entries = []
    for (const key of Reflect.ownKeys(value)) {
      if (typeof key !== 'string') throw new TypeError('Query symbol keys are unsupported')
      const descriptor = Object.getOwnPropertyDescriptor(value, key)
      if (!descriptor.enumerable || !('value' in descriptor)) {
        throw new TypeError('Query properties must be enumerable data properties')
      }
      entries.push([key, encodeQuery(descriptor.value, seen)])
    }
    entries.sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0)
    encoded = ['object', entries]
  }
  seen.delete(value)
  return encoded
}

function canonicalize(query) {
  return JSON.stringify(encodeQuery(query))
}

function decodeQuery(node) {
  const [tag, payload] = node
  if (tag === 'null') return null
  if (tag === 'string' || tag === 'boolean') return payload
  if (tag === 'number') return payload === '-0' ? -0 : Number(payload)
  if (tag === 'array') return payload.map(decodeQuery)
  if (tag === 'object') {
    const result = Object.create(null)
    for (const [key, child] of payload) result[key] = decodeQuery(child)
    return result
  }
  throw new TypeError('Corrupt canonical query key')
}

function decodeCanonicalKey(key) {
  return decodeQuery(JSON.parse(key))
}

function normalizeError(error) {
  const result = {
    name: typeof error?.name === 'string' ? error.name : 'Error',
    message: typeof error?.message === 'string' ? error.message : 'Worker query failed',
  }
  if (typeof error?.code === 'string') result.code = error.code
  return result
}

const emptyRecords = Object.freeze(Object.create(null))
const EMPTY_SERVER_SNAPSHOT = Object.freeze({version: 0, records: emptyRecords})
const IDLE = Object.freeze({status: 'idle', generation: 0})

class WorkerQueryStore {
  #records = new Map()
  #listeners = new Set()
  #refCounts = new Map()
  #lastUsed = new Map()
  #snapshot = EMPTY_SERVER_SNAPSHOT
  #createWorker
  #worker = null
  #workerEpoch = 0
  #nextGeneration = 0
  #closed = false
  #capacity

  constructor(createWorker, {capacity = 50} = {}) {
    if (!Number.isInteger(capacity) || capacity < 1) throw new RangeError('capacity must be positive')
    if (typeof createWorker !== 'function') throw new TypeError('createWorker must be a function')
    this.#createWorker = createWorker
    this.#capacity = capacity
    this.#spawnWorker()
  }

  subscribe = listener => {
    this.#listeners.add(listener)
    return () => this.#listeners.delete(listener)
  }

  getSnapshot = () => this.#snapshot
  getServerSnapshot = () => EMPTY_SERVER_SNAPSHOT

  retain(key) {
    this.#refCounts.set(key, (this.#refCounts.get(key) ?? 0) + 1)
    this.#lastUsed.set(key, performance.now())
  }

  release(key) {
    const next = Math.max(0, (this.#refCounts.get(key) ?? 1) - 1)
    if (next === 0) this.#refCounts.delete(key)
    else this.#refCounts.set(key, next)
    this.#lastUsed.set(key, performance.now())
    this.evictIfNeeded()
  }

  #publish(nextRecords) {
    this.#records = nextRecords
    const view = Object.create(null)
    for (const [key, record] of nextRecords) view[key] = record
    this.#snapshot = Object.freeze({
      version: this.#snapshot.version + 1,
      records: Object.freeze(view),
    })
    for (const listener of this.#listeners) listener()
  }

  #allocateGeneration() {
    if (this.#nextGeneration >= Number.MAX_SAFE_INTEGER) {
      throw new RangeError('Worker query generation exhausted')
    }
    return ++this.#nextGeneration // store 全局单调；record 删除/淘汰也不会 ABA 回绕
  }

  #spawnWorker() {
    if (this.#closed) throw new DOMException('Store closed', 'AbortError')
    const worker = this.#createWorker()
    if (!worker || typeof worker.postMessage !== 'function' ||
        typeof worker.addEventListener !== 'function' || typeof worker.terminate !== 'function') {
      worker?.terminate?.()
      throw new TypeError('createWorker must return a Worker-like object')
    }

    const epoch = ++this.#workerEpoch
    this.#worker = worker
    worker.addEventListener('message', event => {
      if (this.#worker === worker && this.#workerEpoch === epoch) this.onMessage(event.data)
    })
    worker.addEventListener('messageerror', () => {
      this.#handleWorkerCrash(worker, epoch, new Error('Worker message could not be decoded'))
    })
    worker.addEventListener('error', event => {
      event.preventDefault?.()
      this.#handleWorkerCrash(worker, epoch, event.error ?? new Error(event.message || 'Worker crashed'))
    })
    return worker
  }

  #ensureWorker() {
    return this.#worker ?? this.#spawnWorker()
  }

  #handleWorkerCrash(worker, epoch, error) {
    if (this.#closed || this.#worker !== worker || this.#workerEpoch !== epoch) return
    this.#worker = null
    this.#workerEpoch += 1 // 先让旧实例的所有迟到消息失效
    worker.terminate()
    this.onCrash(error)
    try {
      // publish listener 可能重入 query 并已创建实例；ensure 避免再泄漏一个 Worker。
      this.#ensureWorker() // 最多立即尝试一次；失败后由显式 retry 再尝试
    } catch {
      // pending 已进入 retryable error；绝不能重新留成永久 pending。
    }
  }

  query(key) {
    if (this.#closed) return
    const existing = this.#records.get(key)
    if (existing?.status === 'pending' || existing?.status === 'success') return
    const generation = this.#allocateGeneration()
    let worker
    let payload
    try {
      payload = decodeCanonicalKey(key)
      worker = this.#ensureWorker()
    } catch (error) {
      const failed = Object.freeze({
        status: 'error', generation,
        error: immutableResult(normalizeError(error)), retryable: true,
      })
      this.#publish(new Map(this.#records).set(key, failed))
      return
    }
    const pending = Object.freeze({status: 'pending', generation})
    this.#lastUsed.set(key, performance.now())
    this.#publish(new Map(this.#records).set(key, pending))
    try {
      worker.postMessage({type: 'query', key, generation, payload})
    } catch (error) {
      // structured-clone 等同步失败也必须离开 pending，不能制造永久 loading。
      const current = this.#records.get(key)
      if (current?.generation !== generation) return
      const failed = Object.freeze({
        status: 'error',
        generation,
        error: immutableResult(normalizeError(error)),
        retryable: false,
      })
      this.#publish(new Map(this.#records).set(key, failed))
    }
  }

  onMessage(message) {
    if (!message || !['result', 'error', 'cancelled'].includes(message.type)) return
    const current = this.#records.get(message.key)
    // 每个 generation 只接受第一个终态；重复 result/error/cancelled 都幂等忽略。
    if (!current || current.status !== 'pending' ||
        current.generation !== message.generation) return
    if (message.type === 'cancelled') {
      const records = new Map(this.#records)
      records.delete(message.key)
      this.#publish(records) // 取消回到 idle，而不是 error
      return
    }
    let next
    try {
      next = message.type === 'result'
        ? Object.freeze({status: 'success', generation: message.generation, data: immutableResult(message.data)})
        : Object.freeze({
            status: 'error', generation: message.generation,
            error: immutableResult(normalizeError(message.error)),
            retryable: Boolean(message.retryable),
          })
    } catch (error) {
      next = Object.freeze({
        status: 'error', generation: message.generation,
        error: immutableResult(normalizeError(error)), retryable: false,
      })
    }
    this.#publish(new Map(this.#records).set(message.key, next))
    this.evictIfNeeded()
  }

  onCrash(error) {
    let next = new Map(this.#records)
    let changed = false
    for (const [key, record] of next) {
      if (record.status !== 'pending') continue
      next.set(key, Object.freeze({
        status: 'error',
        generation: record.generation,
        error: immutableResult(normalizeError(error)),
        retryable: true,
      }))
      changed = true
    }
    if (changed) this.#publish(next)
  }

  close() {
    if (this.#closed) return
    this.#closed = true
    this.#workerEpoch += 1
    this.#worker?.terminate()
    this.#worker = null
    const next = new Map(this.#records)
    let changed = false
    for (const [key, record] of next) {
      if (record.status !== 'pending') continue
      next.delete(key) // Provider 关闭属于生命周期取消，不伪装成业务 error
      changed = true
    }
    if (changed) this.#publish(next)
  }

  evictIfNeeded() {
    if (this.#records.size <= this.#capacity) return
    const candidates = [...this.#records]
      .filter(([key, record]) => !this.#refCounts.has(key) && record.status !== 'pending')
      .sort(([a], [b]) => (this.#lastUsed.get(a) ?? 0) - (this.#lastUsed.get(b) ?? 0))
    if (!candidates.length) return

    const next = new Map(this.#records)
    for (const [key] of candidates) {
      if (next.size <= this.#capacity) break
      next.delete(key)
      this.#lastUsed.delete(key)
    }
    if (next.size !== this.#records.size) this.#publish(next)
  }
}
```

真实实现不要在 snapshot 内暴露随后会原地改变的 Map；上例每次发布都换 Map，记录也冻结。未变化时返回同一 `#snapshot`，变化后只发布一次新对象。

Provider 可以采用“路由级所有权”：服务端与 hydrate 首帧都渲染同一 fallback，commit 后才创建 Worker；离开这段路由时 Provider 卸载并终止 Worker。这样 SSR render 不产生外部资源，Strict Mode 的额外 setup/cleanup 也保持对称：

```jsx
function WorkerQueryProvider({workerUrl, children, fallback = null}) {
  const [runtime, setRuntime] = useState(null)

  useEffect(() => {
    let nextStore
    try {
      nextStore = new WorkerQueryStore(
        () => new Worker(workerUrl, {type: 'module'}),
        {capacity: 50},
      )
      setRuntime({workerUrl, store: nextStore, error: null})
    } catch (error) {
      setRuntime({workerUrl, store: null, error: normalizeError(error)})
    }

    return () => nextStore?.close()
  }, [workerUrl])

  // SSR 与 hydrate 的初始输出一致；Effect 后才挂载会发查询的消费者。
  if (runtime?.workerUrl !== workerUrl || runtime?.store == null) return fallback
  return <WorkerQueryContext.Provider value={runtime.store}>{children}</WorkerQueryContext.Provider>
}
```

若 Provider 必须常驻全站，则把“最后一个 `release` 后延迟 terminate、下一次 `retain/query` 再创建”做成 store 的显式状态机，并以 generation 隔离旧 Worker 消息；不要仅把句柄置空。上面的路由级策略用 Provider 卸载作为“最后一个消费者离开”的释放边界，简单且可验证。Store 在 Worker `error/messageerror` 后先使旧 epoch 失效、终止旧实例、把 pending 记录发布成 `retryable: true`，再尝试创建替代实例；即使创建失败，显式 retry 也会重新走 `#ensureWorker`，不会留在永久 loading。

Hook：

```jsx
function useWorkerQuery(query) {
  const store = useContext(WorkerQueryContext)
  const key = canonicalize(query)
  const snapshot = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getServerSnapshot)
  const record = snapshot.records[key] ?? IDLE
  const deferredRecord = useDeferredValue(record)

  useEffect(() => {
    store.retain(key)
    store.query(key)
    return () => store.release(key)
  }, [store, key])

  const retry = useCallback(() => store.query(key), [store, key])
  return {record, deferredRecord, isStale: deferredRecord !== record, retry}
}
```

`#publish` 同步替换真实外部 store snapshot；不要把它包在 Transition 中，React 不能把外部 store mutation 标成 non-blocking，且会在相关条件下回退为 blocking。上例只用 `useDeferredValue` 延迟昂贵的**呈现**，同时保留 `record` 代表最新事实。Provider 在 commit 后创建外部资源，或使用客户端专用的惰性 store；SSR snapshot 必须稳定且与服务端 HTML 一致。缓存采用 LRU/TTL，并区分“没有消费者”与“立即销毁”，避免 Strict Mode/快速路由切换导致抖动。

三个不能省的回归组：`{a: undefined}`、`{}` 以及 `[undefined]`、`[null]` 必须是“前者拒绝、后者正常”，不能静默共用 key；`cancelled(key, gen1) → 重查 → 迟到 result(key, gen1)` 不得覆盖 gen2；fake Worker 崩溃且第一次替换构造失败时，pending 先变 retryable error，用户 retry 后第二次构造成功并以新 generation 完成。另测对象键顺序不同但结构相同会去重，旧 Worker epoch 的所有消息均无效。

冻结只覆盖 JSON-like 结果；二进制/TypedArray 应用需要只读 facade 或明确所有权，不能假装 `Object.freeze(typedArray)` 给出了深不可变。缓存较大时，每次重建完整只读对象成本也要测量，可改为每 key 一个小 store 或使用经过验证的持久化数据结构。

每组件 new Worker 会重复复制数据、重复计算、破坏请求去重和缓存、放大线程/内存开销，并让同一 query 得到彼此不一致的快照；它是所有权错误，不只是慢一点。

复写任务：先从空文件实现不带 React 的 store，并用 20 个事件序列测试不变量；最后只写薄 Hook 适配。
