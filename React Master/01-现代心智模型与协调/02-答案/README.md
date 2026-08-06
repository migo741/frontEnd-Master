# 第 01 章参考答案

## 练习一

`pop/unshift` 修改了当前 state 数组，传给 `setTasks` 的仍是同一引用，React 可能跳过更新；即便因别的更新重新渲染，索引 key 仍把 `EditableRow` 的 state 绑定到“第几个位置”，所以任务换位、draft 留在原位置，出现串号。

最小修复：

```tsx
function moveLastToFirst() {
  setTasks(current => {
    if (current.length < 2) return current
    return [current.at(-1)!, ...current.slice(0, -1)]
  })
}

{tasks.map(task => (
  <EditableRow key={task.id} task={task} />
))}
```

若草稿是跨排序保留、统一保存的业务数据，应提升并按 id 存储：

```tsx
const [drafts, setDrafts] = useState<Record<string, string>>(() =>
  Object.fromEntries(tasks.map(t => [t.id, t.title])),
)

function EditableRow({task}: {task: Task}) {
  const value = drafts[task.id] ?? ''
  return (
    <label>
      {task.id}
      <input
        value={value}
        onChange={e => setDrafts(d => ({...d, [task.id]: e.target.value}))}
      />
    </label>
  )
}
```

若每次 task 身份改变就必须丢弃局部草稿，可以让编辑器以 task id 为 key：

```tsx
function Row({task}: {task: Task}) {
  return <Editor key={task.id} initialTitle={task.title} />
}
```

注意：列表本身也仍需 `key={task.id}`。提升状态适合需要跨挂载保存/统一提交；换 key 适合“新实体就是新会话”的明确语义。

测试核心（建议给输入框可访问名称）：

```tsx
it('keeps draft with the task identity after reorder', async () => {
  const user = userEvent.setup()
  render(<TaskBoard />)

  const taskB = screen.getByRole('textbox', {name: /任务 b/i})
  await user.clear(taskB)
  await user.type(taskB, '自定义')
  await user.click(screen.getByRole('button', {name: '末项置顶'}))

  expect(screen.getByRole('textbox', {name: /任务 b/i})).toHaveValue('自定义')
})
```

## 练习二

点击时 `n` 的快照为 0：

| 队列项 | 输入 | 输出 |
|---|---:|---:|
| 替换为 `n + 1` | 0 | 1 |
| `x => x + 10` | 1 | 11 |
| 替换为 `n + 2` | 11 | 2 |

所以点击后的按钮是 2。最后一项使用闭包快照中的 `n`（0）计算出“替换为 2”，不关心队列中间值 11。

一秒后，函数式更新在当时最新 state 2 上加 100，按钮为 102；日志仍打印创建 `click` 闭包时的 `n`，即 0。

若需求是一次点击稳定增加 `1 + 10 + 2 + 100 = 113`，所有变更都应表达为相对前值的更新；如果 100 必须延迟，最终仍是 113：

```tsx
function click() {
  setN(x => x + 1)
  setN(x => x + 10)
  setN(x => x + 2)
  setTimeout(() => setN(x => x + 100), 1000)
}
```

也可把同步的前三项合为 `setN(x => x + 13)`，意图更清楚。

## 复盘答案

state 由 React 保存，并与返回树中的组件身份关联，不是组件函数局部变量长期持有。函数每次调用只拿到对应渲染的快照。同位置同类型通常保留 state；改变 key 会让 React 把它视为新身份。例如 `<Chat key={contactId}>` 切换联系人时重置输入草稿，避免把消息发给错误的人。

