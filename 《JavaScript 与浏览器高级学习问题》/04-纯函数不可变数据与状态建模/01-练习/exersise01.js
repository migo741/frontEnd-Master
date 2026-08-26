// 契约：

// 1. root 只能由普通对象、数组和叶子值组成。
// 2. path 是字符串/非负整数数组，路径必须已经存在。
// 3. updater 恰好调用一次；若结果与旧叶子 `Object.is`，返回原 root。
// 4. 只复制根到叶子的路径，其他分支保持引用相等。
// 5. 不修改输入，保留数组稀疏位置。
// 6. 拒绝 `__proto__`、`prototype`、`constructor` 路径段。

function translateObject(root, path, update) {
  if (path.length === 0) {
    return update
  }
  const [key, ...restPath] = path
  return {
    ...root,
    [key]: translateObject(root[key], restPath, updater),
  }
}

function updateAtPath(root, path, updater) {
  if (typeof root !== "object" && !Array.isArray(root)) return
  let curObj = root
  let index = 0
  while (index < path.length) {
    curObj = curObj[path[index]]
    index++
  }
  const update = updater()
  if (Object.is(update, curObj)) return
  translateObject(root, path, update)
}
