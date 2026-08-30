# 答案与复盘

## 题 1

```css
.settings-form .field:has(:user-invalid) { --control-border: var(--danger); }
.side-nav__section:has(> a[aria-current="page"]) { font-weight: 650; }
.data-table__row:has(> * input:checked) { background: var(--selection-bg); }
```

selector 从组件 root 开始，并尽量使用 child combinator 限定关系。fallback 不是复制完整高级样式：输入自身的 `:user-invalid`、`aria-current` 链接、`:checked` 状态本来就应清晰，因此旧浏览器仍可操作。若产品必须让整行选中视觉在旧浏览器一致，可由应用已有 `data-selected` 状态提供，而非额外 DOM 查询脚本。

## 题 2

```css
@layer components {
  :where(.notice) {
    padding: var(--space-3);
    border-inline-start: .25rem solid var(--notice-accent);

    & > :where(.notice__title) { margin-block: 0 .25rem; }
    &[data-tone="warning"] { --notice-accent: var(--color-warning); }
  }
}

@scope (.article) to (.embedded-widget) {
  :scope h2 { text-wrap: balance; }
  :scope a { text-underline-offset: .15em; }
}
```

基础规则本身已由 `.notice`、`.article` 限制，`@scope` 只改善边界和 proximity；不识别该 at-rule 的浏览器会忽略这段增强，而基础样式仍正确。不要把所有后代写成 `& .a .b .c`；BEM-like element class 并不要求 BEM 命名教条，它提供的是稳定接口。
