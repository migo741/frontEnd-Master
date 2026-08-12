# 第 08 章参考答案

## 练习一：一次建索引，一次投影

原实现的最坏复杂度为 O(orders × users)。10 万乘 2 万不是“JS 不够快”，而是重复做了可以共享的查找工作。

参考实现：

```js
export function joinOrders(orders, users) {
  const usersById = new Map()

  for (const user of users) {
    if (!user || typeof user.id !== 'string' || user.id === '') {
      throw new TypeError('Every user requires a non-empty string id')
    }
    if (usersById.has(user.id)) {
      throw new Error('Duplicate user id: ' + user.id)
    }
    usersById.set(user.id, user)
  }

  let missing = 0
  const rows = orders.map(order => {
    if (!order || typeof order.userId !== 'string') {
      throw new TypeError('Every order requires a string userId')
    }
    const owner = usersById.get(order.userId) ?? null
    if (owner === null) missing += 1
    return {...order, owner}
  })

  return {rows, missing}
}
```

慢速 oracle 应独立表达相同契约：

```js
function joinOrdersSlow(orders, users) {
  const ids = new Set()
  for (const user of users) {
    if (ids.has(user.id)) throw new Error('Duplicate user id: ' + user.id)
    ids.add(user.id)
  }
  let missing = 0
  const rows = orders.map(order => {
    const owner = users.find(user => user.id === order.userId) ?? null
    if (owner === null) missing += 1
    return {...order, owner}
  })
  return {rows, missing}
}
```

随机测试生成小规模唯一用户、含缺失引用的订单，深比较两版；重复 id 用单独负例，因为两版都必须先拒绝。基准时不要把随机数据生成计入被测阶段，也不要在循环中打印。

如果 users 只有 5 个、orders 只有 2 个且只执行一次，Map 的分配和复杂度未必值得；保持简单实现并写出规模假设更合理。若索引跨多次查询复用，还要定义 users 更新后如何失效，不能长期拿旧实体。

## 练习二：Fenwick Tree 维护动态前缀

Fenwick Tree 用 1-based tree 数组保存分段和。单点变化只更新覆盖该位置的 O(log n) 个节点；前缀和也沿最低有效位向父级跳转。

完整参考实现：

```js
export class HeightIndex {
  #heights
  #tree

  constructor(heights) {
    this.#heights = Float64Array.from(heights)
    this.#tree = new Float64Array(this.#heights.length + 1)
    for (let i = 0; i < this.#heights.length; i += 1) {
      this.#assertHeight(this.#heights[i])
      this.#add(i, this.#heights[i])
    }
  }

  get length() {
    return this.#heights.length
  }

  get totalHeight() {
    return this.offsetOf(this.length)
  }

  update(index, nextHeight) {
    if (!Number.isInteger(index) || index < 0 || index >= this.length) {
      throw new RangeError('Height index out of range: ' + index)
    }
    this.#assertHeight(nextHeight)
    const delta = nextHeight - this.#heights[index]
    this.#heights[index] = nextHeight
    this.#add(index, delta)
  }

  offsetOf(endExclusive) {
    if (!Number.isInteger(endExclusive) || endExclusive < 0 || endExclusive > this.length) {
      throw new RangeError('Prefix boundary out of range: ' + endExclusive)
    }
    let sum = 0
    for (let i = endExclusive; i > 0; i -= i & -i) {
      sum += this.#tree[i]
    }
    return sum
  }

  rowAt(offset) {
    if (this.length === 0) return -1
    const safe = Math.min(Math.max(0, offset), this.totalHeight)
    const count = this.#countWhilePrefix(safe, true)
    return Math.min(count, this.length - 1)
  }

  visibleRange({scrollTop, viewportHeight, overscan = 0}) {
    for (const [name, value] of Object.entries({scrollTop, viewportHeight, overscan})) {
      if (!Number.isFinite(value) || value < 0) {
        throw new RangeError(name + ' must be a finite non-negative number')
      }
    }
    if (this.length === 0 || viewportHeight === 0) return {start: 0, end: 0}

    const top = Math.min(this.totalHeight, Math.max(0, scrollTop - overscan))
    const bottom = Math.min(
      this.totalHeight,
      scrollTop + viewportHeight + overscan,
    )
    if (top >= this.totalHeight || bottom <= top) {
      return {start: this.length, end: this.length}
    }

    const start = this.rowAt(top)
    const end = Math.min(
      this.length,
      this.#countWhilePrefix(bottom, false) + 1,
    )
    return {start, end}
  }

  #add(index, delta) {
    for (let i = index + 1; i < this.#tree.length; i += i & -i) {
      this.#tree[i] += delta
    }
  }

  #countWhilePrefix(limit, allowEqual) {
    let count = 0
    let sum = 0
    let bit = 1
    while ((bit << 1) <= this.length) bit <<= 1

    for (; bit !== 0; bit >>= 1) {
      const next = count + bit
      if (next > this.length) continue
      const candidate = sum + this.#tree[next]
      const accepted = allowEqual ? candidate <= limit : candidate < limit
      if (accepted) {
        count = next
        sum = candidate
      }
    }
    return count
  }

  #assertHeight(value) {
    if (!Number.isFinite(value) || value <= 0) {
      throw new RangeError('Row height must be a finite positive number')
    }
  }
}
```

关键边界：

- `rowAt` 求“有多少完整行的底部小于等于 offset”，所以刚好落在边界时进入下一行；
- end 是半开边界，求“有多少行底部严格小于 viewport bottom”再加一；
- 滚动超过总高返回空尾区间，不把最后一行伪装为仍可见；
- TypedArray 固定长度，插入/删除行需要重建、分块 Fenwick，或选择平衡树。

随机验证可维护普通 heights 数组，每次 update 同步修改；oracle 用线性累加计算 offset 与 visible range。固定 seed，失败时打印 seed 和操作序列，便于复现。

ResizeObserver 回调不应立刻反复写尺寸并触发自身。把 `id -> latestHeight` 合并到 Map，在下一帧一次更新索引；若更新了锚点之前的行高，总差值应补到 `scrollTop`，保持锚点视觉位置。用户正在主动滚动时可延后补偿或限制幅度。

## 取舍与复写任务

| 方案 | 前缀查询 | 单点更新 | 内存 | 适用 |
|---|---:|---:|---:|---|
| 固定行高公式 | O(1) | O(1) | O(1) | 高度真正固定 |
| 全量前缀数组 | O(1) | O(n) | O(n) | 几乎不更新 |
| Fenwick Tree | O(log n) | O(log n) | O(n) | 高频测量更新 |

关闭答案，先独立复写 `#add` 与 `offsetOf`，再只看方法签名写出二进制 lifting。最后用 3 行手算树验证边界，不要靠“随机测试都绿”替代理解。
