# 第 01 章练习

先创建 `chapter-01` 路由或独立页面。不要看答案，先写出你对每个 bug 的因果链。

## 练习一：会“串号”的可编辑清单

下面代码同时包含身份、不可变性和快照问题：

```tsx
type Task = {id: string; title: string}

export function TaskBoard() {
  const [tasks, setTasks] = useState<Task[]>([
    {id: 'a', title: '读讲义'},
    {id: 'b', title: '做练习'},
    {id: 'c', title: '写复盘'},
  ])

  function moveLastToFirst() {
    const last = tasks.pop()!
    tasks.unshift(last)
    setTasks(tasks)
  }

  return (
    <>
      <button onClick={moveLastToFirst}>末项置顶</button>
      {tasks.map((task, index) => <EditableRow key={index} task={task} />)}
    </>
  )
}

function EditableRow({task}: {task: Task}) {
  const [draft, setDraft] = useState(task.title)
  return <input value={draft} onChange={e => setDraft(e.target.value)} />
}
```

任务：

1. 先预测点击“末项置顶”后会发生什么；分别解释不更新和输入草稿串号的根因。
2. 修复排序和 key。
3. 产品新增“切换任务时，未保存草稿必须重置”为明确需求。给两种方案：提升 draft 状态；或用 key 有意重置。说明各自适用约束。
4. 添加测试：在第二行输入“自定义”，置顶后草稿仍跟随任务 `b`，而不是留在第二个位置。

验收：没有直接修改 state；key 来自实体身份；测试用角色/标签查询输入框，不查实现细节。

## 练习二：手算更新队列（高难）

不运行，先写出按钮文本和 1 秒后的日志：

```tsx
function QueuePuzzle() {
  const [n, setN] = useState(0)

  function click() {
    setN(n + 1)
    setN(x => x + 10)
    setN(n + 2)
    setTimeout(() => {
      setN(x => x + 100)
      console.log('snapshot:', n)
    }, 1000)
  }

  return <button onClick={click}>{n}</button>
}
```

任务：

1. 写出点击后本批更新的折叠表。
2. 说明为什么最后一个 `setN(n + 2)` 会覆盖前面折叠出的中间结果。
3. 1 秒后 state 与日志分别是什么？
4. 改写为“每次点击确定增加 113”，无论批处理边界如何变化都不依赖旧快照。

## 复盘交付

用不超过 200 字解释：“state 属于组件函数，还是属于 React 树中的位置？”给一个 key 改变导致重置的例子。

