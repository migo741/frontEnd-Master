# 答案与复盘

## 题 1

```css
.drawer {
  transition: transform 180ms cubic-bezier(.2,.8,.2,1),
              opacity 140ms linear,
              display 180ms allow-discrete;
}
.drawer:not(:popover-open) { opacity: 0; transform: translateX(1rem); }
@starting-style {
  .drawer:popover-open { opacity: 0; transform: translateX(1rem); }
}
@media (prefers-reduced-motion: reduce) {
  .drawer { transition-duration: 1ms; transform: none; }
  .skeleton { animation: none; }
}
```

具体 pseudo-class/离散过渡支持要按目标浏览器验证；fallback 是瞬时显示隐藏。不要用 `transition: all`，它可能在后续维护时意外动画尺寸或颜色。Skeleton 在慢请求中表达结构即可，不应持续闪烁吸引注意。

## 题 2

```ts
const update = () => router.push(target)
if (!document.startViewTransition || matchMedia('(prefers-reduced-motion: reduce)').matches) {
  update()
} else {
  document.startViewTransition(update)
}
```

`view-transition-name` 在同一时刻必须唯一；列表 item 只给被导航实体命名，结束后清理。固定 header 可放独立 transition group，避免随页面快照移动。异步数据若不能及时到达，先过渡 shell，再以普通状态加载，不把导航挂在动画上。

Scroll-driven 部分放进 `@supports (animation-timeline: scroll())`，基础进度可缺失但正文不能隐藏；reduced motion 直接展示内容。

