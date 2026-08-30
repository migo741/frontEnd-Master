# 答案与复盘

## 题 1

```css
.user-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: .75rem;
  align-items: start;
}
.user-card__body { min-inline-size: 0; }
.user-card__email { overflow-wrap: anywhere; }
.user-card__badges { display: flex; flex-wrap: wrap; gap: .25rem; }
.user-card__actions { flex: none; }
```

`minmax(0, 1fr)` 允许中列收缩，`overflow-wrap:anywhere` 为无自然断点文本提供机会。若产品决定邮箱单行省略，应通过 title 以外的可聚焦 disclosure/copy action 提供完整值，因为 title 在触摸和键盘上不可靠。

测试至少生成 worst-case fixtures，而不是只改一个示例姓名。

## 题 2

```css
.auth-page {
  min-block-size: 100vh;
  min-block-size: 100svh;
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
}
.auth-page__content { overflow: auto; min-block-size: 0; }
.auth-page__footer {
  padding-block-end: max(1rem, env(safe-area-inset-bottom));
}
```

`svh` 适合确保内容在浏览器 UI 展开时也放得下；需要随工具栏变化实时填充的场景可评估 `dvh`，但频繁尺寸变化可能带来视觉跳动。键盘属于 visual viewport 的复杂行为，不能仅靠固定底栏；让主要内容可滚动、焦点能 scroll into view 更稳健。第一行 `100vh` 是语法 fallback，后支持声明覆盖它。

