# 第 09 章参考答案

## 练习一：把事件翻译为显式命令

误触的根因通常是把整行设为隐式点击目标，再靠子节点 stopPropagation 打补丁。参考方案只让带 `data-action` 的按钮产生领域命令：

```js
export function bindTaskList(list, commands) {
  const controller = new AbortController()
  // 当没有相邻按钮可接收焦点时，list 作为程序化 fallback；-1 不进入普通 Tab 顺序。
  if (!list.hasAttribute('tabindex')) list.tabIndex = -1

  list.addEventListener('click', event => {
    if (!(event.target instanceof Element)) return
    const actionElement = event.target.closest('[data-action]')
    if (!actionElement || !list.contains(actionElement)) return

    const row = actionElement.closest('[data-task-id]')
    if (!row || !list.contains(row)) return
    const id = row.dataset.taskId
    if (!id) return

    switch (actionElement.dataset.action) {
      case 'open':
        commands.openTask(id)
        break
      case 'delete': {
        const nextFocus =
          row.nextElementSibling?.querySelector('[data-action="open"]') ??
          row.previousElementSibling?.querySelector('[data-action="open"]') ??
          list
        commands.deleteTask(id)
        row.remove()
        if (nextFocus instanceof HTMLElement) nextFocus.focus()
        break
      }
    }
  }, {signal: controller.signal})

  return () => controller.abort()
}

export function createTaskRow(task) {
  const row = document.createElement('li')
  row.dataset.taskId = String(task.id)

  const checkbox = document.createElement('input')
  checkbox.type = 'checkbox'
  checkbox.checked = Boolean(task.done)
  checkbox.setAttribute('aria-label', '完成：' + task.title)

  const title = document.createElement('span')
  title.textContent = task.title

  const open = document.createElement('button')
  open.type = 'button'
  open.dataset.action = 'open'
  open.setAttribute('aria-label', '打开：' + task.title)
  open.append(makeIcon('open'))

  const remove = document.createElement('button')
  remove.type = 'button'
  remove.dataset.action = 'delete'
  remove.setAttribute('aria-label', '删除：' + task.title)
  remove.append(makeIcon('delete'))

  row.append(checkbox, title, open, remove)
  return row
}
```

`makeIcon` 生成 SVG 时应给装饰图标 `aria-hidden="true"`，按钮的可访问名称放在按钮本身。任务标题只经 `textContent`/属性 API 写入，不拼 HTML。

测试应实际 dispatch/click 最内层 path，确认 `closest` 找到 button；动态 append 后无需重新 bind；调用 dispose 后再 click，命令计数不增加。删除焦点策略必须是产品契约：这里选择下一行、上一行、最后回列表，不能让焦点无声掉到 body。

## 练习二：用 dialog 平台语义承载模态

建议 HTML：

```html
<h2 id="project-list-heading" tabindex="-1">项目列表</h2>
<dialog id="delete-dialog" aria-labelledby="delete-title" aria-describedby="delete-detail">
  <form method="dialog">
    <h2 id="delete-title">删除项目？</h2>
    <p id="delete-detail">此操作无法撤销。</p>
    <p id="delete-error" role="alert" hidden></p>
    <button value="cancel" autofocus>取消</button>
    <button value="confirm" data-confirm>确认删除</button>
  </form>
</dialog>
```

控制器需要把网络状态与 dialog close 分开：

```js
export function createDeleteDialog({dialog, fallbackFocus, deleteProject}) {
  const form = dialog.querySelector('form')
  const confirm = dialog.querySelector('[data-confirm]')
  const cancel = dialog.querySelector('button[value="cancel"]')
  const errorBox = dialog.querySelector('[role="alert"]')
  const controller = new AbortController()
  let opener = null
  let projectId = null
  let submitting = false
  let requestController = null
  let generation = 0
  let disposed = false

  function restoreFocus() {
    const target = opener?.isConnected ? opener : fallbackFocus
    if (target instanceof HTMLElement) target.focus()
    opener = null
  }

  function open({id, trigger}) {
    if (disposed || dialog.open || submitting) return
    projectId = id
    opener = trigger
    errorBox.hidden = true
    errorBox.textContent = ''
    dialog.showModal()
  }

  dialog.addEventListener('click', event => {
    if (event.target !== dialog || submitting) return
    const rect = dialog.getBoundingClientRect()
    const inside =
      event.clientX >= rect.left && event.clientX <= rect.right &&
      event.clientY >= rect.top && event.clientY <= rect.bottom
    if (!inside) dialog.close('cancel')
  }, {signal: controller.signal})

  dialog.addEventListener('cancel', event => {
    if (submitting) event.preventDefault()
  }, {signal: controller.signal})

  dialog.addEventListener('close', restoreFocus, {
    signal: controller.signal,
  })

  form.addEventListener('submit', async event => {
    const intent = event.submitter?.value
    if (intent !== 'confirm') {
      // method=dialog 的取消按钮也会 submit；提交中必须显式阻止它关闭。
      if (submitting) event.preventDefault()
      return
    }
    event.preventDefault()
    if (submitting) return

    submitting = true
    confirm.disabled = true
    cancel.disabled = true
    confirm.setAttribute('aria-describedby', 'delete-error')
    errorBox.hidden = true
    const currentGeneration = ++generation
    const currentProjectId = projectId
    requestController = new AbortController()

    try {
      await deleteProject(currentProjectId, {signal: requestController.signal})
      if (disposed || currentGeneration !== generation) return
      dialog.close('confirm')
    } catch (error) {
      if (disposed || currentGeneration !== generation || requestController.signal.aborted) return
      errorBox.textContent =
        error instanceof Error ? error.message : '删除失败，请重试'
      errorBox.hidden = false
      confirm.focus()
    } finally {
      if (currentGeneration === generation && !disposed) {
        submitting = false
        requestController = null
        confirm.disabled = false
        cancel.disabled = false
      }
    }
  }, {signal: controller.signal})

  function dispose() {
    if (disposed) return
    disposed = true
    generation += 1
    requestController?.abort(new DOMException('Dialog disposed', 'AbortError'))
    controller.abort()
    if (dialog.open) dialog.close('dispose')
    restoreFocus()
  }

  return {open, dispose}
}
```

原生 modal dialog 会让文档其余部分 inert 并管理 Tab 边界，但应用仍负责可访问名称、业务状态、错误提示、重复提交和焦点返回。若目标浏览器不支持 `showModal`，应在能力检测后加载经过测试的 modal 实现，不要把非模态 div 冒充降级。

测试证据：

- 从两个 opener 分别打开并关闭，焦点回到各自触发者；
- Tab/Shift+Tab 不进入背景，Escape 在 idle 关闭、submitting 不关闭；
- 坐标在 rect 外的 backdrop click 关闭，rect 内不关闭；
- reject 后 dialog 仍 open、alert 可见、确认按钮可重试；
- opener 删除后，焦点回到列表标题；
- 提交期间取消按钮、Escape 与 backdrop 均不能关闭；dispose 会 abort 请求，迟到结果不操作 UI；
- dispose 后再触发旧引用不会有 listener 泄漏。

## 边界与复写任务

服务端删除仍需权限、幂等和冲突处理；disabled button 只是前端防重复体验。关闭答案后，先从状态转换表复写控制器，再只用键盘完成一次失败后重试；最后在 DevTools Accessibility tree 口述每个节点的 name、role 与 state。
