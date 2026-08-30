# 答案与复盘

## 题 1

修复顺序：先让 DOM/语义正确，再移除固定高度/nowrap，允许 Grid/Flex item 收缩和换行，最后调整视觉。不要用 tabindex 正数重排一个错误 DOM；它会制造另一套难维护顺序。

```css
.focusable:focus-visible { outline: 3px solid var(--focus-ring); outline-offset: 3px; }
.card { min-block-size: 0; block-size: auto; }
@media (width < 40rem) { .layout { grid-template-columns: 1fr; } }
```

人工检查包括：跳过链接、Tab/Shift+Tab、焦点不被 sticky 遮挡、Escape/方向键协议、200/400% reflow、错误文本、hover/focus 内容、读屏名称和状态。

## 题 2

```css
@media (forced-colors: active) {
  .selected, .button, .control { border: 1px solid currentColor; }
  .selected { outline: 2px solid Highlight; }
}
@media (prefers-reduced-motion: reduce) {
  .parallax, .auto-carousel { animation: none; transform: none; }
  .button { transition-duration: 1ms; }
}
@media (hover: none) { .icon-button { min-inline-size: 44px; min-block-size: 44px; } }
@media print { nav, .toolbar { display: none; } .details { display: block; } }
```

系统强制色下不要隐藏原生 form appearance。打印前检查分页、孤行、URL/日期/金额和敏感信息；CSS print 不是随意把所有内容显示出来。

