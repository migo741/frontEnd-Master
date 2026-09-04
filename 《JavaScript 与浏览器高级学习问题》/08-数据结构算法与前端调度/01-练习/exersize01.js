// ## 练习一：把订单投影从嵌套扫描改成索引

// 实现 `joinOrders(orders, users)`。现有代码对每个订单调用一次 `users.find`，10 万订单、2 万用户时明显阻塞。

// 要求：

// - 输出保持订单原顺序，不修改任一输入或实体对象；
// - 先构建 `userId -> user` 索引，总时间目标 O(users + orders)；
// - 重复 user id 立即失败，错误包含 id；
// - 找不到 owner 的订单保留，但输出 `owner: null` 并汇总 missing 数；
// - 无效 id、空数组和同一用户被大量订单引用都有测试；
// - 保留慢速实现作为测试 oracle，对随机小数据比较两版结果；
// - 在固定数据、同一设备上各运行至少 20 次，报告 p50/p95 与常驻内存变化。

// 验收：不能只给 `console.time` 截图；解释什么数据规模下仍会选择简单的 `find` 版本。

const IsIdLawful = (id) => {
  return Number.isInteger(id) && id >= 0
}

const joinOrders = function (orders, users) {
  const userMap = new Map()
  for (const user of users) {
    if (!IsIdLawful(user.id)) {
      throw new Error(`Error:Invalid user id ${user.id}`)
    }
    if (userMap.has(user.id))
      throw new Error(`Error:userId is repeat ${user.id}`)
    userMap.set(user.id, user)
  }
  let missing = 0
  const result = orders.map((order) => {
    if (!IsIdLawful(order.userId) || !userMap.get(order.userId)) {
      missing++
      return {
        ...order,
        owner: null,
      }
    }

    return {
      ...order,
      owner: userMap.get(order.userId),
    }
  })
  return {
    orders: result,
    missing,
  }
}
