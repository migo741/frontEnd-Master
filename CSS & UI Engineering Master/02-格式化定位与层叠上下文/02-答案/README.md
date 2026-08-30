# 答案与复盘

## 题 1

可靠的 App Shell 通常让页面或主区只有一个 owner：

```css
html, body, #app { min-block-size: 100%; }

.app {
  min-block-size: 100dvh;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
}

.app__body {
  min-block-size: 0;
  display: grid;
  grid-template-columns: 16rem minmax(0, 1fr);
}

.app__main { min-inline-size: 0; overflow: auto; }
.app__sidebar { position: sticky; inset-block-start: 0; align-self: start; }
```

关键常是 `minmax(0, 1fr)`、`min-block-size: 0` 和明确 overflow owner，而非更多 height。Grid/Flex item 默认 min-size 会阻止它缩到可滚动范围。

## 题 2

先在 DevTools Layers/Elements 中向上找 transform、opacity、isolation 与 overflow。局部 tooltip 如果允许被组件边界约束，可由明确 positioned container 承担；若必须跨越裁切边界，使用 Popover/top layer 或 portal/Teleport，而不是让 overflow 全局 visible 破坏卡片。

```css
:root {
  --z-base: 0;
  --z-sticky: 10;
  --z-dropdown: 20;
}

dialog { border: 0; }
dialog::backdrop { background: rgb(0 0 0 / .45); }
```

top layer 的顺序由进入顺序管理，不再与普通 z-index 竞争。CSS 答案必须配合原生 dialog/Popover 的语义、焦点和 Escape 行为；用 div 模仿外观不算完成。

