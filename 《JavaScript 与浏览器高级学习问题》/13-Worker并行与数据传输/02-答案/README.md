# 第 13 章参考答案

## 练习一

核心不是“把函数文件改名为 worker”，而是确定所有权与代次：原始 buffer 一次性转给 Worker，主线程不再读取；查询只传小消息；结果提交由 generation 守门。

主线程骨架：

```js
export function createAnalyzer(url, source) {
  if (!(source instanceof Float64Array) || !(source.buffer instanceof ArrayBuffer)) {
    throw new TypeError('source must be a Float64Array backed by transferable ArrayBuffer')
  }
  const worker = new Worker(url, {type: 'module'})
  let generation = 0
  let closed = false
  let terminalReason = null
  const pending = new Map()

  const signalReason = signal => signal && 'reason' in signal
    ? signal.reason
    : new DOMException('Aborted', 'AbortError')

  const fail = error => {
    if (closed) return false
    closed = true
    terminalReason = error
    for (const job of pending.values()) job.reject(error)
    pending.clear()
    worker.terminate()
    return true
  }

  worker.onmessage = ({data}) => {
    if (closed) return
    if (!data || typeof data !== 'object' ||
        !Number.isInteger(data.generation) ||
        !['result', 'error'].includes(data.type)) {
      fail(new Error('Invalid analyzer worker message'))
      return
    }
    const job = pending.get(data.generation)
    if (!job) return
    pending.delete(data.generation)
    if (data.type === 'error') job.reject(Object.assign(new Error(data.message), {name: data.name}))
    else job.resolve(data)
  }

  worker.addEventListener('error', event => {
    event.preventDefault?.()
    fail(event.error instanceof Error
      ? event.error
      : new Error(event.message || 'Analyzer worker crashed'))
  })
  worker.addEventListener('messageerror', () => {
    fail(new Error('Analyzer worker message could not be deserialized'))
  })

  try {
    worker.postMessage({
      type: 'init',
      buffer: source.buffer,
      byteOffset: source.byteOffset,
      length: source.length,
    }, [source.buffer])
  } catch (error) {
    fail(error)
    throw error
  }

  return {
    query(options, signal) {
      if (closed) return Promise.reject(terminalReason)
      const current = ++generation
      for (const [old, job] of pending) {
        try {
          worker.postMessage({type: 'cancel', generation: old})
        } catch (error) {
          fail(error)
          break
        }
        job.reject(new DOMException('Superseded', 'AbortError'))
        pending.delete(old)
      }
      if (closed) return Promise.reject(terminalReason)

      return new Promise((resolve, reject) => {
        if (signal?.aborted) return reject(signalReason(signal))
        const abort = () => {
          const job = pending.get(current)
          if (!job) return
          pending.delete(current)
          try {
            worker.postMessage({type: 'cancel', generation: current})
          } catch (error) {
            fail(error) // 同时拒绝仍在等待的其他查询
          }
          job.reject(signalReason(signal))
        }
        signal?.addEventListener('abort', abort, {once: true})
        pending.set(current, {
          resolve: value => { signal?.removeEventListener('abort', abort); resolve(value) },
          reject: error => { signal?.removeEventListener('abort', abort); reject(error) },
        })
        try {
          worker.postMessage({type: 'query', generation: current, options})
        } catch (error) {
          const job = pending.get(current)
          pending.delete(current)
          job?.reject(error)
        }
      })
    },
    close() {
      return fail(new DOMException('Analyzer closed', 'AbortError'))
    },
  }
}
```

Worker 端必须主动检查取消：

```js
let values
const cancelled = new Set()
const active = new Set()

self.onmessage = ({data}) => {
  if (data.type === 'init') {
    values = new Float64Array(data.buffer, data.byteOffset, data.length)
  }
  // 已经完成的 generation 不再收 cancel，避免迟到 cancel 永久堆在 Set。
  if (data.type === 'cancel' && active.has(data.generation)) {
    cancelled.add(data.generation)
  }
  if (data.type === 'query') run(data).catch(error => {
    postMessage({type: 'error', generation: data.generation, name: error.name, message: error.message})
  })
}

async function run({generation, options}) {
  active.add(generation)
  try {
    const started = performance.now()
    const buckets = new Uint32Array(options.bucketCount)
    for (let i = 0; i < values.length; i++) {
      if ((i & 1023) === 0) {
        if (cancelled.delete(generation)) throw new DOMException('Aborted', 'AbortError')
        await new Promise(resolve => setTimeout(resolve, 0)) // 给 cancel 消息处理机会
      }
      const normalized = normalize(values[i], options)
      if (matches(normalized, options)) buckets[toBucket(normalized, options)]++
    }
    postMessage({type: 'result', generation, buckets, computeMs: performance.now() - started}, [buckets.buffer])
  } finally {
    active.delete(generation)
    cancelled.delete(generation)
  }
}
```

紧密循环不让出 Worker 自己的事件循环时，cancel 消息也无法被处理；因此检查标记之外还要按块让出。块大小需要用取消延迟和吞吐量共同校准。

测试应故意让旧查询更慢，并断言调用方只提交最新代。还要分别触发 Worker `error` 与 `messageerror`，断言当时全部 pending 使用同一个终止原因拒绝、监听清理、Worker 被 terminate；之后每次 query 都立即拒绝且不再 postMessage。close 连续调用两次只终止一次。注意 `source.buffer.byteLength === 0` 是 transfer 成功的证据，也是主线程不得再使用它的提醒。

## 练习二

推荐状态：任务 `queued -> running -> fulfilled | rejected | cancelled`；Worker `idle -> busy -> crashed -> replaced | closed`。任务 id 与 attempt 共同构成消息身份，避免旧实例迟到消息误完成重试：

```js
{version: 1, type: 'run', id, attempt, operation, payload}
{version: 1, type: 'result', id, attempt, value}
{version: 1, type: 'cancel', id, attempt}
```

下面是覆盖题目关键状态的最小可运行调度核心。Worker 端仍需实现相同消息 schema 和协作式 cancel：

```js
const PRIORITY = {background: 0, 'user-visible': 1, 'user-blocking': 2}

class BackpressureError extends Error {
  constructor(message = 'Worker queue is full') {
    super(message)
    this.name = 'BackpressureError'
  }
}

function abortReason(signal) {
  // AbortSignal.reason 可以显式为 null；不能用 ?? 改写调用方语义。
  return signal && 'reason' in signal
    ? signal.reason
    : new DOMException('Aborted', 'AbortError')
}

export class WorkerScheduler {
  #url
  #createWorker
  #maxQueued
  #cancelGraceMs
  #queue = []
  #running = new Map()
  #slots = []
  #sequence = 0
  #closed = false

  constructor(url, {
    size = 3,
    maxQueued = 20,
    cancelGraceMs = 1000,
    createWorker = value => new Worker(value, {type: 'module'}),
  } = {}) {
    if (!Number.isInteger(size) || size < 1) throw new RangeError('size must be positive')
    if (!Number.isInteger(maxQueued) || maxQueued < 0) throw new RangeError('maxQueued must be non-negative')
    if (!Number.isFinite(cancelGraceMs) || cancelGraceMs < 0) throw new RangeError('cancelGraceMs must be non-negative')
    this.#url = url
    this.#createWorker = createWorker
    this.#maxQueued = maxQueued
    this.#cancelGraceMs = cancelGraceMs
    this.#slots = Array.from({length: size}, () => ({worker: null, generation: 0, task: null}))
    try {
      for (const slot of this.#slots) this.#spawn(slot)
    } catch (error) {
      // 构造器不会返回半初始化实例；此前成功创建的 Worker 必须全部回收。
      this.#shutdown(error)
      throw error
    }
  }

  run(operation, payload, {
    priority = 'background',
    signal,
    idempotent = false,
  } = {}) {
    if (!(priority in PRIORITY)) return Promise.reject(new TypeError('unknown priority'))
    if (this.#closed) return Promise.reject(new DOMException('Scheduler closed', 'AbortError'))

    return new Promise((resolve, reject) => {
      const task = {
        id: crypto.randomUUID(),
        operation,
        payload,
        priority,
        rank: PRIORITY[priority],
        sequence: this.#sequence++,
        attempt: 0,
        idempotent,
        signal,
        resolve,
        reject,
        status: 'new',
        settled: false,
        slot: null,
        cancelTimer: 0,
        onAbort: null,
      }

      task.onAbort = () => this.#cancel(task, abortReason(signal))
      if (signal?.aborted) {
        this.#settle(task, 'reject', abortReason(signal))
        return
      }
      signal?.addEventListener('abort', task.onAbort, {once: true})

      const idleSlot = this.#slots.find(slot => !slot.task)
      if (idleSlot) {
        this.#start(idleSlot, task)
        return
      }

      if (this.#queue.length >= this.#maxQueued) {
        // 高优先任务只能替换一个更低优先的排队任务；总队列仍保持有界。
        let victimIndex = -1
        for (let i = this.#queue.length - 1; i >= 0; i--) {
          if (this.#queue[i].rank < task.rank) { victimIndex = i; break }
        }
        if (victimIndex < 0) {
          this.#settle(task, 'reject', new BackpressureError())
          return
        }
        const [victim] = this.#queue.splice(victimIndex, 1)
        this.#settle(victim, 'reject', new BackpressureError('Evicted by a higher-priority task'))
      }

      task.status = 'queued'
      this.#insert(task)
      this.#dispatch()
    })
  }

  close() {
    this.#shutdown(new DOMException('Scheduler closed', 'AbortError'))
  }

  #insert(task) {
    this.#queue.push(task)
    this.#queue.sort((a, b) => b.rank - a.rank || a.sequence - b.sequence)
  }

  #dispatch() {
    if (this.#closed) return
    for (const slot of this.#slots) {
      while (!slot.task && this.#queue.length) {
        const task = this.#queue.shift()
        if (task.settled) continue
        if (task.signal?.aborted) {
          this.#settle(task, 'reject', abortReason(task.signal))
          continue // 继续为同一个空 slot 寻找下一项，不能让队列卡住
        }
        this.#start(slot, task)
      }
    }
  }

  #start(slot, task) {
    task.status = 'running'
    task.slot = slot
    slot.task = task
    this.#running.set(task.id, task)
    try {
      slot.worker.postMessage({
        version: 1,
        type: 'run',
        id: task.id,
        attempt: task.attempt,
        operation: task.operation,
        payload: task.payload,
      })
    } catch (error) {
      // 例如 payload 无法 structured-clone：任务失败，但 Worker 本身仍可复用。
      this.#settle(task, 'reject', error)
      this.#release(slot, task)
    }
  }

  #cancel(task, reason) {
    if (task.settled) return
    if (task.status === 'queued') {
      const index = this.#queue.indexOf(task)
      if (index >= 0) this.#queue.splice(index, 1)
      this.#settle(task, 'reject', reason)
      this.#dispatch()
      return
    }
    if (task.status === 'running') {
      const slot = task.slot
      const generation = slot.generation
      try {
        slot.worker.postMessage({
          version: 1, type: 'cancel', id: task.id, attempt: task.attempt,
        })
      } catch (error) {
        // Worker 已不可通信：调用方按自己的取消原因结束，并立即替换坏实例。
        this.#settle(task, 'reject', reason)
        this.#crash(slot, generation, error)
        return
      }
      this.#settle(task, 'reject', reason) // 调用方立即结束；slot 等 Worker 确认后释放
      task.cancelTimer = setTimeout(() => {
        if (slot.task === task) this.#crash(slot, generation, new Error('Worker ignored cancellation'))
      }, this.#cancelGraceMs)
    }
  }

  #onMessage(slot, generation, message) {
    if (this.#closed || generation !== slot.generation) return
    const task = slot.task
    if (!task || message?.version !== 1 || message.id !== task.id || message.attempt !== task.attempt) return
    if (!['result', 'error', 'cancelled'].includes(message.type)) return

    if (!task.settled) {
      if (message.type === 'result') this.#settle(task, 'resolve', message.value)
      else if (message.type === 'error') this.#settle(task, 'reject', Object.assign(new Error(message.error?.message), message.error))
      else this.#settle(task, 'reject', new DOMException('Cancelled by worker', 'AbortError'))
    }
    this.#release(slot, task)
  }

  #release(slot, task) {
    if (slot.task !== task) return
    clearTimeout(task.cancelTimer)
    this.#running.delete(task.id)
    task.slot = null
    slot.task = null
    this.#dispatch()
  }

  #crash(slot, generation, cause) {
    if (this.#closed || generation !== slot.generation) return
    const task = slot.task
    if (task) {
      clearTimeout(task.cancelTimer)
      this.#running.delete(task.id)
      task.slot = null
      slot.task = null
    }

    try {
      this.#spawn(slot) // 先增加 generation 并替换实例，旧实例迟到消息自动失效
    } catch (spawnError) {
      const failure = new AggregateError(
        [cause, spawnError],
        'Worker crashed and its replacement could not be created',
        {cause: spawnError},
      )
      // 当前任务已经从 slot 脱离，必须显式 settle；随后关闭调度器，
      // 否则无 Worker 的空 slot 会让队列永久悬挂。
      if (task && !task.settled) this.#settle(task, 'reject', failure)
      this.#shutdown(failure)
      return
    }

    if (task && !task.settled) {
      if (task.signal?.aborted) {
        this.#settle(task, 'reject', abortReason(task.signal))
      } else if (task.idempotent && task.attempt === 0) {
        task.attempt += 1
        task.status = 'queued'
        this.#insert(task)
      } else {
        this.#settle(task, 'reject', cause)
      }
    }
    this.#dispatch()
  }

  #spawn(slot) {
    const generation = ++slot.generation
    const previous = slot.worker
    if (previous) {
      try {
        previous.terminate()
      } catch (error) {
        // 保留引用，让构造回滚/#shutdown 可以再次尝试清理。
        throw error
      }
    }
    slot.worker = null

    let worker = null
    try {
      worker = this.#createWorker(this.#url)
      if (!worker || typeof worker.postMessage !== 'function' ||
          typeof worker.addEventListener !== 'function' ||
          typeof worker.terminate !== 'function') {
        throw new TypeError('createWorker must return a Worker-compatible object')
      }
      worker.addEventListener('message', event => this.#onMessage(slot, generation, event.data))
      worker.addEventListener('messageerror', () => this.#crash(slot, generation, new Error('Worker message error')))
      worker.addEventListener('error', event => {
        event.preventDefault?.()
        this.#crash(slot, generation, event.error ?? new Error(event.message || 'Worker crashed'))
      })
      slot.worker = worker
    } catch (error) {
      // createWorker 返回实例后，后续校验或监听安装失败也不能泄漏它。
      try { worker?.terminate?.() } catch {}
      slot.worker = null
      throw error
    }
  }

  #shutdown(reason) {
    if (this.#closed) return false
    this.#closed = true
    for (const task of this.#queue.splice(0)) this.#settle(task, 'reject', reason)
    for (const slot of this.#slots) {
      const task = slot.task
      if (task && !task.settled) this.#settle(task, 'reject', reason)
      clearTimeout(task?.cancelTimer)
      if (task) task.slot = null
      slot.task = null
      slot.generation += 1
      try { slot.worker?.terminate() } catch {}
      slot.worker = null
    }
    this.#running.clear()
    return true
  }

  #settle(task, kind, value) {
    if (task.settled) return
    task.settled = true
    task.status = kind === 'resolve' ? 'fulfilled' : 'rejected'
    task.signal?.removeEventListener('abort', task.onAbort)
    if (kind === 'resolve') task.resolve(value)
    else task.reject(value)
  }
}
```

这份实现选择：高优先任务可驱逐一个更低优先的**排队**任务，但不能让队列越界；取消运行任务先拒绝调用方，再等待 Worker 的匹配消息释放 slot，超时则替换该 Worker；只有声明为幂等且从未因崩溃重试过的任务自动重试一次。生产中还应限制 payload、校验返回 schema、记录排队/执行/取消时长，并让错误序列化保留可审计错误码而非任意对象赋值。

关键测试使用可控 fake worker，不依赖真实耗时：手动发送 result/error/crash，验证并发上限、优先级 FIFO、所有队列路径有界、队首已 abort 后后续仍启动、取消最多 settle 一次、close 全部拒绝、崩溃只重试一次幂等任务、旧 generation 消息无效。让第 N 次 createWorker 抛错，断言构造器此前创建的 N-1 个实例全部 terminate；让替换 Worker 创建失败，断言原运行任务及所有排队/运行任务均拒绝且无 Promise 悬挂；让 addEventListener 安装中途失败，断言刚返回的 Worker 也被 terminate。第一次崩溃后幂等任务的 attempt 从 0 变 1 且只重试一次，第二次崩溃必须拒绝，createWorker 失败不额外消费一次“幽灵重试”。`Promise.race` 只挑最早完成的 Promise，既不限制任务启动，也不管理 Worker 生命周期、优先级、消息身份或背压。

复写任务：关闭答案，实现一个 `size: 1` 的版本；先让排队/运行/取消/close 完全正确，再扩到多个 slot 和崩溃替换。
