# 答案与复盘

## 题 1

```css
.metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 16rem), 1fr));
  grid-auto-rows: auto auto 1fr auto;
  gap: 1rem;
}
.metric {
  display: grid;
  grid-row: span 4;
  grid-template-rows: subgrid;
}
```

fallback 可先定义卡片为普通 grid/flex，再在 `@supports (grid-template-rows: subgrid)` 中增强对齐。核心内容顺序不能依赖 subgrid。注意所有卡片都 span 4 行时，父级轨道分组和 DOM 结构必须一致；复杂可变 slot 需要重新审视是否值得跨卡片对齐。

## 题 2

外层可用命名区域，表单字段本身用 subgrid 或显式列：

```css
.settings {
  display: grid;
  grid-template-columns: minmax(10rem, 14rem) minmax(0, 1fr) minmax(12rem, 18rem);
  grid-template-areas: "nav form help";
  gap: clamp(1rem, 3vw, 2rem);
}

@media (width < 60rem) {
  .settings { grid-template-columns: 1fr; grid-template-areas: "nav" "form" "help"; }
}
```

若帮助侧栏在 DOM 中位于表单之后，这个视觉顺序与阅读顺序一致。不要用 dense 自动填充交互字段。表单错误应占自己的行或允许内容推开后续项，固定行高会剪掉翻译和缩放文本。

