// 要求：

// 1. 默认 trailing 调用，可配置 `leading` 与 `trailing`。
// 2. 包装函数必须透传动态 `this` 和全部参数。
// 3. 提供 `cancel()`、`flush()`、`pending()`。
// 4. `flush()` 返回最近一次实际调用的结果；同步函数不能被强制改成 Promise。
// 5. 没有待执行调用时，`flush()` 不得重复执行 fn。
// 6. 用 fake timer 覆盖连续调用、leading-only、leading+trailing、取消与 flush。

// 先写状态表：空闲、等待、已 leading 调用，各事件如何迁移。

function debounce(fn, wait, options = {}) {
  let { leading = false, trailing = true } = options
  let timerId = null
  let currentFnStatu = null
  let lastThis = null
  let lastArgs = null
  let lateRes

  const returnFn = function (...args) {
    const shouldCallLeading = leading && timerId === null
    if (shouldCallLeading) {
      lateRes = fn.apply(this, args)
    }
    if (timerId) {
      clearTimeout(timerId)
    }
    lastThis = this
    lastArgs = [...args]
    timerId = setTimeout(() => {
      timerId = null
      if (trailing) {
        lateRes = fn.apply(this, args)
      }
    }, wait)
  }

  returnFn.cancel = function () {
    clearTimeout(timerId)
    timerId = null
  }
  returnFn.flush = function (...args) {
    if (timerId) {
      clearTimeout(timerId)
      timerId = null
      if (trailing) {
        lateRes = fn.apply(lastThis, lastArgs)
      }
    }
    return lateRes
  }
  returnFn.pending = function () {
    return timerId !== null
  }
  return returnFn
}
const fn1 = debounce(() => {}, 1000)
fn1()
