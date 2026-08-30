# 答案与复盘

## 题 1

```css
.toolbar { display: flex; flex-wrap: wrap; gap: .75rem; align-items: center; }
.toolbar__heading { flex: 0 1 auto; }
.toolbar__search { flex: 1 1 18rem; min-inline-size: min(100%, 14rem); }
.toolbar__filters { display: flex; flex: 1 1 auto; flex-wrap: wrap; gap: .5rem; }
.toolbar__primary { flex: 0 0 auto; }
```

真正的实现要根据 DOM 顺序和可用宽度校准 basis，不要照抄数字。最小宽度用 `min(100%, 14rem)` 防止在更窄容器中反向造成 overflow。若业务要求主按钮在新行占满，可用容器查询改变 flex-basis，而不是 `order` 把它视觉移动到阅读顺序之前。

## 题 2

集合使用 Grid 产生等高 tracks；每张卡内部用 column flex，把 CTA 通过 `margin-block-start:auto` 推向可用空间末端：

```css
.plans { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 17rem), 1fr)); gap: 1rem; }
.plan { display: flex; flex-direction: column; }
.plan__features { flex: 1 1 auto; }
.plan__cta { margin-block-start: auto; }
```

推荐 badge 最好预留统一 slot 或在 Grid/Subgrid 中对齐，不能 absolute 覆盖文字。固定卡片高度会在翻译、缩放和增项时失败。

