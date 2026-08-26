// 要求：

// 1. `construct` 实现普通用户函数的 new 四步语义。
// 2. 构造器返回对象/函数时采用其返回值，返回原始值时仍返回新实例。
// 3. prototype 不是对象时，按普通构造语义回退到 `Object.prototype`。
// 4. `ordinaryInstanceOf` 沿原型链判断，但必须明确拒绝 `Symbol.hasInstance` 自定义语义。
// 5. 测试 null、箭头函数、被修改的 prototype、返回函数的构造器。

// 最后写出为什么这两个实现不能完全替代 `Reflect.construct` 和原生 `instanceof`。

const isComplexValue = (val) => {
  if (val !== null && (typeof val === "object" || typeof val === "function"))
    return true
  return false
}

function construct(Constructor, ...args) {
  const obj = isComplexValue(Constructor.prototype)
    ? Object.create(Constructor.prototype)
    : Object.create(Object.prototype)
  let res = Constructor.apply(obj, args)
  if (isComplexValue(res)) {
    return res
  }
  return obj
}

function ordinaryInstanceOf(value, Constructor) {
  let prototype = Object.getPrototypeOf(value)
  while (prototype !== null) {
    if (Constructor.prototype === prototype) return true
    prototype = Object.getPrototypeOf(prototype)
  }
  return false
}
