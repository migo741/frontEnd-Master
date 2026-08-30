# 答案与复盘

## 题 1

一种 8 测试组合：纯函数单测 2 个（权限矩阵、冲突合并规则）；组件测试 4 个（无权限不渲染、键盘选择、pending 防重复、409 恢复 UI）；repository 集成 1 个（错误映射/request id）；E2E 1 个（管理员转派成功并在列表看到新负责人）。网络重试若属于通用 client，应在 client 单测，不在本 feature 重测。

删除“组件默认 props 大快照”：它对核心风险几乎无保护，文案/DOM 调整会制造噪音。覆盖率只是遗漏线索，不能决定测试价值。

## 题 2

```ts
it('recovers from an assignment conflict', async () => {
  server.use(http.post('/api/tickets/42/assignee', async () => {
    await gate.promise
    return HttpResponse.json({ code: 'VERSION_CONFLICT', requestId: 'r-1' }, { status: 409 })
  }))
  render(AssignDialog, { props: { ticketId: '42' }, global: { plugins } })

  await user.click(screen.getByRole('button', { name: '确认转派' }))
  expect(screen.getByRole('button', { name: '确认转派' })).toBeDisabled()
  gate.resolve()
  expect(await screen.findByText('工单已被他人更新')).toBeVisible()

  server.use(http.get('/api/tickets/42', () => HttpResponse.json(latestTicket)))
  await user.click(screen.getByRole('button', { name: '加载最新版本' }))
  expect(await screen.findByDisplayValue(latestTicket.assigneeName)).toBeVisible()
})
```

`gate` 是测试拥有的 deferred Promise，使 pending 状态确定可控；`findBy` 等待用户可见结果，不依赖 100ms 魔法数字。高级答案还应断言 pending 时快速双击只有一个 POST，并且冲突 UI 展示 requestId 供排障但不泄露敏感堆栈。

