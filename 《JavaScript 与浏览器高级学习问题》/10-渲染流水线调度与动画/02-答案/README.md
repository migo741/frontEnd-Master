# 第 10 章参考答案

## 练习一：减少跨阶段往返

慢版本的因果链是：写样式使布局失效 → 读几何迫使浏览器同步完成 style/layout → 下一行再写使其失效 → 再读。2,000 行把本可批量完成的工作拆成大量往返。

如果目标只是两列布局，首选 CSS：

```css
.rows {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
```

若业务确实需要测量，建立明确阶段：

```js
export function bindMeasuredRows(container, renderSummary) {
  const controller = new AbortController()
  let frame = 0

  function schedule() {
    cancelAnimationFrame(frame)
    frame = requestAnimationFrame(() => {
      frame = 0
      const width = container.clientWidth
      const rows = [...container.querySelectorAll('[data-row]')]

      // mutate：同批写
      const nextWidth = Math.floor(width / 2)
      for (const row of rows) row.style.width = nextWidth + 'px'

      // measure：第一次读取可能触发布局，但循环内不再穿插写
      let totalHeight = 0
      for (const row of rows) {
        totalHeight += row.getBoundingClientRect().height
      }

      // 将汇总写入与被测列表分离，避免下一次读取前反复污染
      renderSummary({count: rows.length, totalHeight})
    })
  }

  window.addEventListener('resize', schedule, {
    signal: controller.signal,
    passive: true,
  })
  schedule()

  return () => {
    controller.abort()
    cancelAnimationFrame(frame)
  }
}
```

这段实现仍可能在第一处几何读取触发一次 layout；它的目标是消除 N 次交替。若 `renderSummary` 改变列表几何，应移到测量之后且不要在同帧再次读取列表。

证据应比较相同 resize 手势与数据：慢版 trace 有密集的 Layout/Forced Reflow，修复后布局次数显著减少；若 JS query/循环仍是长任务，再考虑缓存节点、虚拟化或减少数据。CSS 方案若满足需求，通常连 resize listener 与测量都可删除。

## 练习二：先得到最终布局，再播放差值

参考实现假设卡片自身没有业务 transform；真实组件可给卡片增加专用动画 wrapper，避免覆盖业务 transform。

```js
const activeAnimations = new WeakMap()

export function animateReorder(
  container,
  reorder,
  {duration = 220, easing = 'cubic-bezier(.2,.8,.2,1)'} = {},
) {
  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches
  const beforeElements = [...container.querySelectorAll('[data-id]')]
  const first = new Map()

  // First：先读完当前视觉位置，不能在循环中取消/写 transform
  for (const element of beforeElements) {
    const id = element.dataset.id
    if (!id || first.has(id)) throw new Error('Missing or duplicate data-id: ' + id)
    first.set(id, element.getBoundingClientRect())
  }

  // 所有读取后再取消旧动画；同一 task 内的瞬时 snap 不会被绘制
  for (const element of beforeElements) {
    activeAnimations.get(element)?.cancel()
    activeAnimations.delete(element)
    for (const animation of element.getAnimations()) animation.cancel()
  }

  reorder()

  const afterElements = [...container.querySelectorAll('[data-id]')]
  const last = new Map()
  for (const element of afterElements) {
    const id = element.dataset.id
    if (!id || last.has(id)) throw new Error('Missing or duplicate data-id: ' + id)
    last.set(id, element.getBoundingClientRect())
  }

  if (reduceMotion) return {finished: Promise.resolve(), cancel() {}}

  const animations = []
  for (const element of afterElements) {
    const from = first.get(element.dataset.id)
    const to = last.get(element.dataset.id)
    if (!from || !to) continue // 新增项使用独立淡入策略

    const dx = from.left - to.left
    const dy = from.top - to.top
    if (dx === 0 && dy === 0) continue

    const animation = element.animate(
      [
        {transform: 'translate(' + dx + 'px, ' + dy + 'px)'},
        {transform: 'translate(0, 0)'},
      ],
      {duration, easing, fill: 'none'},
    )
    activeAnimations.set(element, animation)
    animation.finished
      .catch(() => {}) // cancel 会 reject finished
      .finally(() => {
        if (activeAnimations.get(element) === animation) {
          activeAnimations.delete(element)
        }
      })
    animations.push(animation)
  }

  return {
    finished: Promise.allSettled(animations.map(item => item.finished)),
    cancel() {
      for (const animation of animations) animation.cancel()
    },
  }
}
```

连续排序时 First 在取消前读取 `getBoundingClientRect`，其中包含旧动画的当前视觉 transform；随后所有动画在一次 task 内取消、DOM 重排、再从视觉位置动画到新布局，因此不会先绘制中间 snap。

边界：

- 删除项在重排后已不存在，要想离场动画需克隆到 overlay，且移除可访问树/focus；
- 新增项没有 First，可选择短淡入或无动画；
- 容器在 First/Last 之间滚动会污染差值，应锁定同步重排阶段或把 scroll delta 纳入计算；
- 元素已有 transform 时使用动画 wrapper、CSS individual translate 或矩阵组合；
- reorder 必须同步完成，不能在两个 await 之间保留过期几何；
- DOM 移动同一节点通常保留焦点；若被删，必须有显式焦点策略。

测试不应等待真实 220ms。注入 duration 0 或 mock `Element.animate`，断言每个 animation 被取消、最终顺序正确、重复 id 报错。Performance 中动画期间应主要看到 composite，而不是每帧 Layout；若 Paint 仍高，检查阴影、滤镜、巨大图层与图片。

## 复写任务

关闭答案后只记住四个词：First、Last、Invert、Play。先写无取消的 3 项版本，录制 trace；再加入连续排序与 reduced motion。若无法解释每一次几何读取发生在哪个布局状态，就还没有掌握。
