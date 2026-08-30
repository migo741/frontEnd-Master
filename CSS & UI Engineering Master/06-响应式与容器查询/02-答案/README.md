# 答案与复盘

## 题 1

```css
.order-host { container: order / inline-size; }
.order { display: grid; gap: .75rem; }
.order__row { display: grid; gap: .25rem; }

@container order (width >= 34rem) {
  .order__row {
    grid-template-columns: minmax(0, 2fr) minmax(6rem, 1fr) auto;
    align-items: baseline;
  }
}
```

完整实现应保留每行 label，不能为了桌面列头在窄版失去语义。可以在宽容器视觉隐藏重复 label，但需确保 accessibility name 仍存在。命名 query 避免匹配外层最近的无关 container。

## 题 2

```css
.hero__title { font-size: clamp(2rem, 1.3rem + 3vw, 4.75rem); line-height: 1.05; }
.hero__copy { max-inline-size: 62ch; font-size: clamp(1rem, .94rem + .3vw, 1.25rem); }
.hero { padding-block: clamp(3rem, 8vw, 8rem); }
```

`clamp` 中间项只是流体函数，不应让大屏字号无限增长。结构断点由“文案与截图并列后各自低于最小可用宽度”触发，而不是照搬 768/1024。验证 400% 缩放时等效窄宽布局仍可读；CTA 不要仅因视觉需要颠倒 DOM 顺序。

