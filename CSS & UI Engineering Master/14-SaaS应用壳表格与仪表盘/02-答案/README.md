# 答案与复盘

## 题 1

```css
.shell {
  min-block-size: 100svh;
  display: grid;
  grid-template: "header header header" auto
                 "nav main aside" minmax(0, 1fr)
                 / auto minmax(0, 1fr) auto;
}
.shell__header { grid-area: header; z-index: var(--z-sticky); }
.shell__main { grid-area: main; min-inline-size: 0; min-block-size: 0; overflow: auto; scroll-padding-block: 4rem; }
```

移动端优先改 Grid areas/列，不复制 DOM。若顶栏需要随页面而非 main 滚动，重新选择 overflow owner，而不是叠加第二个 auto。使用 `scroll-padding`/`scroll-margin` 防 sticky 遮挡跳转焦点；仍需真机测试虚拟键盘。

## 题 2

HTML table 外包一层：

```css
.table-scroll { overflow: auto; max-inline-size: 100%; }
th { position: sticky; inset-block-start: 0; background: var(--surface-raised); z-index: 2; }
th:first-child, td:first-child { position: sticky; inset-inline-start: 0; background: var(--surface); }
thead th:first-child { z-index: 3; }
[data-density="compact"] { --row-pad: .375rem; --control-size: 2.5rem; }
```

z-index 只在这一个局部 context 中有限分级。Sticky cells 必须覆盖后方内容但保留可见 focus outline。Skeleton 用与真实列相同轨道/高度；error/empty 通过表格 caption 外的状态区域或合适 colspan 呈现，不能破坏 header 语义。

