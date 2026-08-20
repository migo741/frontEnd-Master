// 要求：

// 1. 保留调用时动态 `this`，不能永久绑定 object。
// 2. 保留参数、同步返回值和同步抛错；不能把同步方法统一改成 async。
// 3. 若返回 Promise/thenable，after/error 应在其完成后收到耗时与结果/错误。
// 4. `restore()` 幂等，只恢复自己安装的包装，不能覆盖后来者的修改。
// 5. hook 自身失败不能改变原方法结果，但应交给 `onHookError`。
// 6. 至少测试借用方法、class 私有字段、同步异常、异步拒绝和重复恢复。

//`hooks` 可含 `before(meta)`、`after(meta)`、`error(meta)`。

const isThenAble = (val) => {
  return (
    val !== null &&
    (typeof val === "object" || typeof val === "function") &&
    typeof val.then === "function"
  )
}
const wrapperTryCatch = function (fn, handleError) {
  try {
    fn()
  } catch (wrapperError) {
    handleError(wrapperError)
  }
}

const observeMethod = function (object, key, hooks) {
  if (typeof object[key] !== "function") return
  const { before, after, error, onHookError } = hooks
  const original = object[key]

  const wrapper = function (...args) {
    let result
    let startTime
    const meta = {
      object,
      key,
      thisArgs: this,
      args: [...args],
    }
    wrapperTryCatch(
      () => before(meta),
      (wrapperError) => onHookError(wrapperError),
    )
    try {
      startTime = Date.now()
      result = original.apply(this, args)
    } catch (e) {
      wrapperTryCatch(
        () => error(e),
        (wrapperError) => onHookError(wrapperError),
      )
      throw e
    }
    if (isThenAble(result)) {
      return Promise.resolve(result).then(
        (val) => {
          wrapperTryCatch(
            () => {
              let diffTime = Date.now() - startTime
              after({
                ...meta,
                val,
                duration: diffTime,
              })
            },
            (wrapperError) => onHookError(wrapperError),
          )
          return val
        },
        (e) => {
          wrapperTryCatch(
            () => error(e),
            (wrapperError) => onHookError(wrapperError),
          )
          throw e
        },
      )
    } else {
      wrapperTryCatch(
        () => {
          ;() => {
            let diffTime = Date.now() - startTime
            after({
              ...meta,
              result,
              duration: diffTime,
            })
          }
        },
        () => onHookError(wrapperError),
      )
      return result
    }
  }
  object[key] = wrapper
  return function () {
    if (object[key] === wrapper) {
      object[key] = original
    }
  }
}

const useA = {
  print(a) {
    console.log(a)
  },
}
const restore = observeMethod(useA, print, {
  before(meta) {
    console.log("提前执行", meta)
  },
})
