# 第 11 章参考答案

## 练习一：把 304 当成对已有表示的确认

关键因果链：ETag 标识服务器选择的表示版本；客户端携带 `If-None-Match`，304 只表示对应表示未变，不带新 JSON。没有本地表示就无法解释 304。

参考实现省略业务 Schema，但完整处理 Fetch/缓存生命周期：

```js
export function createDocumentLoader({
  fetchImpl = fetch,
  timeoutMs = 5000,
  identity = () => 'public',
} = {}) {
  const cache = new Map()
  const latestGeneration = new Map()

  function linkSignal(external) {
    const controller = new AbortController()
    const onAbort = () => controller.abort(external.reason)
    if (external?.aborted) controller.abort(external.reason)
    else external?.addEventListener('abort', onAbort, {once: true})
    const timer = setTimeout(() => controller.abort('timeout'), timeoutMs)
    return {
      signal: controller.signal,
      dispose() {
        clearTimeout(timer)
        external?.removeEventListener('abort', onAbort)
      },
    }
  }

  async function load(input, {signal, accept = 'application/json'} = {}) {
    const url = new URL(input, location.href)
    url.hash = ''
    // 用结构化 tuple，避免 URL/Accept/identity 中分隔符造成 key 碰撞。
    const key = JSON.stringify([url.href, accept, identity()])
    const generation = Symbol('document-load')
    latestGeneration.set(key, generation)
    const cached = cache.get(key)
    const headers = new Headers({Accept: accept})
    if (cached?.etag) headers.set('If-None-Match', cached.etag)
    const linked = linkSignal(signal)

    try {
      const response = await fetchImpl(url, {
        method: 'GET',
        headers,
        signal: linked.signal,
      })
      const requestId =
        (response.headers.get('x-request-id') ?? '').slice(0, 128)

      if (response.status === 304) {
        if (!cached) {
          throw Object.assign(new Error('304 without cached representation'), {
            kind: 'protocol',
            requestId,
          })
        }
        return {data: structuredClone(cached.data), source: 'validated-cache'}
      }

      if (!response.ok) {
        throw Object.assign(new Error('HTTP ' + response.status), {
          kind: 'http',
          status: response.status,
          requestId,
        })
      }

      const contentType = response.headers.get('content-type') ?? ''
      if (!contentType.toLowerCase().includes('application/json')) {
        throw Object.assign(new Error('Expected JSON response'), {
          kind: 'protocol',
          requestId,
        })
      }

      let data
      try {
        data = await response.json()
      } catch (cause) {
        throw Object.assign(new Error('Invalid JSON', {cause}), {
          kind: 'decode',
          requestId,
        })
      }

      const stored = structuredClone(data)
      if (latestGeneration.get(key) === generation) {
        cache.set(key, {
          etag: response.headers.get('etag'),
          data: stored,
        })
      }
      return {data: structuredClone(stored), source: 'network'}
    } catch (error) {
      if (linked.signal.aborted) {
        throw Object.assign(new Error('Request aborted', {cause: error}), {
          kind: 'aborted',
          reason: linked.signal.reason,
        })
      }
      if (error?.kind) throw error
      throw Object.assign(new Error('Network failure', {cause: error}), {
        kind: 'network',
      })
    } finally {
      linked.dispose()
      if (latestGeneration.get(key) === generation) {
        latestGeneration.delete(key)
      }
    }
  }

  return {
    load,
    clear() {
      cache.clear()
      // 让所有仍在途的 generation 失效，迟到响应只能返回给原调用者。
      latestGeneration.clear()
    },
  }
}
```

`structuredClone` 隔离调用者修改，但会增加时间/内存，且不是所有值都可克隆。更常见的领域约定是解析后数据只读、开发环境 freeze，并让缓存层拥有更新；这里用 clone 让题目的“不篡改”可观察。

这份 Map 没实现 Cache-Control、Vary 全语义、容量、持久化和跨页面复用，所以不能代替浏览器 HTTP cache。练习价值在于理解 304；生产应优先正确响应头，再由 Query 层协调领域 stale/订阅。

同 key 并发调用彼此独立：每个调用者得到自己请求的结果/错误，只有“最后启动”的 generation 能更新共享 cache。若较新的请求失败，较旧请求仍可返回给自己的调用者，但不能回填 cache；cache 保留并发前最后一次已验证值。`clear()` 还会使全部在途写入失效。

测试除让 304 的 `json` 成为一调用就抛错的 spy，还要用可控 Promise 启动同 key 的 A、B：先返回 B(new ETag)，再返回 A(old ETag)，第三次请求必须携带 B 的 ETag；A/B 调用者仍各自收到对应文档。再测 B 失败、A 后成功不会回填，以及 clear 后迟到响应不会重建 cache。取消后检查外部 signal listener 与 timeout 都清理。

## 练习二：序列是领域一致性的最小证据

参考核心只接受已解析消息，不负责网络 framing：

```js
function cloneJson(value, seen = new WeakSet()) {
  if (value === null || typeof value === 'string' || typeof value === 'boolean') {
    return value
  }
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (Array.isArray(value)) {
    if (seen.has(value)) throw new Error('Cyclic protocol payload')
    seen.add(value)
    const result = value.map(item => cloneJson(item, seen))
    seen.delete(value)
    return result
  }
  if (value && (Object.getPrototypeOf(value) === Object.prototype ||
    Object.getPrototypeOf(value) === null)) {
    if (seen.has(value)) throw new Error('Cyclic protocol payload')
    seen.add(value)
    const result = Object.create(null)
    for (const key of Object.keys(value).sort()) {
      result[key] = cloneJson(value[key], seen)
    }
    seen.delete(value)
    return result
  }
  throw new Error('Protocol payload must be finite JSON data')
}

function fingerprint(message) {
  return JSON.stringify(message)
}

export class SequencedInventory {
  #sequence = 0
  #items = new Map()
  #buffer = new Map()
  #stale = true
  #hasBaseline = false
  #recover
  #maxBuffered
  #metrics

  constructor({recover, maxBuffered = 1000, metrics = {count() {}, gauge() {}}}) {
    this.#recover = recover
    this.#maxBuffered = maxBuffered
    this.#metrics = metrics
  }

  accept(message) {
    this.#assertEnvelope(message)
    if (message.type === 'snapshot') return this.#acceptSnapshot(message)
    const normalized = this.#normalizeDelta(message)

    if (normalized.sequence <= this.#sequence) {
      this.#metrics.count('inventory.duplicate')
      return
    }

    if (normalized.sequence === this.#sequence + 1 && !this.#stale) {
      this.#applyDelta(normalized)
      this.#drain()
      return
    }

    const existing = this.#buffer.get(normalized.sequence)
    if (existing) {
      if (existing.fingerprint !== fingerprint(normalized)) {
        throw new Error(
          'Conflicting inventory events at sequence ' + normalized.sequence,
        )
      }
      this.#metrics.count('inventory.duplicate')
      return
    }

    this.#buffer.set(normalized.sequence, {
      message: normalized,
      fingerprint: fingerprint(normalized),
    })
    this.#metrics.gauge('inventory.buffer', this.#buffer.size)
    if (this.#buffer.size > this.#maxBuffered) {
      this.#buffer.clear()
      this.#stale = true
      this.#metrics.count('inventory.buffer_overflow')
      this.#recover({mode: 'full', after: this.#sequence})
      return
    }
    this.#markGap()
  }

  snapshot() {
    return Object.freeze({
      sequence: this.#sequence,
      stale: this.#stale,
      items: Object.freeze(
        [...this.#items.values()].map(item => Object.freeze(structuredClone(item))),
      ),
    })
  }

  #acceptSnapshot(message) {
    if (message.sequence < this.#sequence) {
      this.#metrics.count('inventory.stale_snapshot')
      return
    }
    if (!Array.isArray(message.items)) throw new Error('Snapshot items must be an array')
    const ids = new Set()
    const normalizedItems = []
    for (const item of message.items) {
      if (!item || typeof item.id !== 'string' || item.id === '' || ids.has(item.id)) {
        throw new Error('Invalid or duplicate snapshot item id')
      }
      ids.add(item.id)
      normalizedItems.push(cloneJson(item))
    }
    normalizedItems.sort((a, b) => a.id < b.id ? -1 : a.id > b.id ? 1 : 0)
    const nextFingerprint = fingerprint({
      type: 'snapshot',
      sequence: message.sequence,
      items: normalizedItems,
    })

    if (message.sequence === this.#sequence && this.#hasBaseline) {
      if (nextFingerprint !== this.#currentSnapshotFingerprint()) {
        throw new Error(
          'Conflicting inventory snapshots at sequence ' + message.sequence,
        )
      }
      this.#metrics.count('inventory.duplicate_snapshot')
      if (this.#stale) {
        this.#stale = false
        this.#drain()
        if (this.#buffer.size > 0) this.#markGap()
      }
      return
    }

    // 所有输入先验证并克隆，之后才一次性替换当前状态。
    this.#items = new Map(normalizedItems.map(item => [item.id, item]))
    this.#sequence = message.sequence
    this.#hasBaseline = true
    for (const sequence of this.#buffer.keys()) {
      if (sequence <= this.#sequence) this.#buffer.delete(sequence)
    }
    this.#stale = false
    this.#drain()
    if (this.#buffer.size > 0) this.#markGap()
  }

  #currentSnapshotFingerprint() {
    const items = [...this.#items.values()]
      .slice()
      .sort((a, b) => a.id < b.id ? -1 : a.id > b.id ? 1 : 0)
    return fingerprint({
      type: 'snapshot',
      sequence: this.#sequence,
      items,
    })
  }

  #drain() {
    while (!this.#stale && this.#buffer.has(this.#sequence + 1)) {
      const sequence = this.#sequence + 1
      const entry = this.#buffer.get(sequence)
      // entry 在入 buffer 前已完整验证；先成功应用，再删除。
      this.#applyDelta(entry.message)
      this.#buffer.delete(sequence)
    }
    this.#metrics.gauge('inventory.buffer', this.#buffer.size)
  }

  #applyDelta(message) {
    if (message.type === 'upsert') {
      this.#items.set(message.item.id, message.item)
    } else {
      this.#items.delete(message.id)
    }
    this.#sequence = message.sequence
  }

  #normalizeDelta(message) {
    if (message.type === 'upsert') {
      if (!message.item || typeof message.item.id !== 'string' || message.item.id === '') {
        throw new Error('Invalid upsert item')
      }
      return {
        type: 'upsert',
        sequence: message.sequence,
        item: cloneJson(message.item),
      }
    }
    if (message.type === 'remove') {
      if (typeof message.id !== 'string' || message.id === '') {
        throw new Error('Invalid remove id')
      }
      return {type: 'remove', sequence: message.sequence, id: message.id}
    }
    throw new Error('Unknown inventory event: ' + message.type)
  }

  #markGap() {
    if (this.#stale) return
    this.#stale = true
    this.#metrics.count('inventory.gap_recovery')
    this.#recover({mode: 'snapshot', after: this.#sequence})
  }

  #assertEnvelope(message) {
    if (!message || !Number.isSafeInteger(message.sequence) || message.sequence < 0) {
      throw new Error('Invalid inventory sequence')
    }
  }
}
```

启动时 stale=true，必须先有 snapshot；这防止“连接建立但没有基线”被显示成可信数据。gap 期间 delta 只进有界 buffer，不提交到 UI。snapshot 是服务器权威：低于当前 sequence 的迟到 snapshot 被忽略；可接受的 snapshot 先完整验证，再原子替换，丢弃 `<= snapshot.sequence` 的 buffer，最后连续 drain。

必须有四组回归测试：

1. 先接受 snapshot 10、delta 11，再送迟到 snapshot 9；断言 sequence/items 仍是 11 的状态，stale snapshot 指标加一。
2. 同 sequence 的 snapshot 即使 item/字段顺序不同，只要规范化内容相同就计 duplicate 且不覆盖；相同 sequence、不同内容抛 protocol error，items/stale/buffer 原样保留。
3. gap 中缓冲 sequence 13；相同内容的 13 再到只计 duplicate，内容不同的 13 抛 protocol error，原 buffer 不被覆盖。
4. 非法 upsert/remove 在进入 buffer 前就失败；随后送 snapshot 不会触发“先 delete 后 apply”的半状态。另测 snapshot 10 + buffer 12/11 后重新接受相同 snapshot 10，可按 11、12 drain 到稳定状态。

适配器伪码：

```text
connect(after=store.sequence)
  on message -> parse/validate -> store.accept
  on heartbeat timeout -> close
  on unexpected close -> full-jitter backoff reconnect(after)
  on store recover -> fetch snapshot -> store.accept(snapshot)
abort
  clear heartbeat/reconnect timers
  detach handlers
  close socket
  ignore every late callback by generation id
```

WebSocket 入站没有业务级背压。buffer 到上限必须关连接并全量恢复；只有协议明确“同一 SKU 的中间价格可合并”时才能 coalesce，库存扣减/审计事件不能擅自丢。

## 边界与复写任务

多标签页、服务器集群和离线队列仍可能产生更高层冲突；sequence 只在其定义的 stream/partition 内有意义。关闭答案后先复写 `accept` 的四分支：旧、连续、缺口、snapshot，再用纸手算 `40, 42, 41, snapshot 43, 44` 的状态变化。最后写一个 buffer=2 的溢出测试。
