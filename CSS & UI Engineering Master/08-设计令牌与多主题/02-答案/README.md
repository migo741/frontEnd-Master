# 答案与复盘

## 题 1

```css
@layer tokens {
  :root {
    --neutral-0: oklch(100% 0 0);
    --neutral-950: oklch(18% .02 255);
    --space-1: .25rem;
    --space-2: .5rem;

    --surface-canvas: var(--neutral-0);
    --text-primary: var(--neutral-950);
    --border-default: oklch(85% .02 255);

    --button-primary-bg: var(--action-primary);
    --button-primary-fg: var(--on-action-primary);
  }
}
```

不要把 `--color-1` 改名为 `--primary` 就宣布语义化。检查每个使用点表达的是 surface、text、border、action 还是 status。数据可视化还需形状/纹理/label，不能用红绿作为唯一通道。

## 题 2

优先级建议：用户显式属性最高；没有显式值时，系统偏好可覆盖租户默认的明暗模式；租户只提供品牌 token。服务端可根据 cookie 输出 `data-theme`，客户端在 CSS 前的极小内联脚本读取已知合法值，避免首帧错误主题。脚本失败时 CSS 系统偏好仍工作。

```css
:root { color-scheme: light dark; }
@media (prefers-color-scheme: dark) { :root:not([data-theme]) { /* dark semantic tokens */ } }
[data-theme="dark"] { color-scheme: dark; /* dark semantic tokens */ }
@media (forced-colors: active) {
  .button { border: 1px solid ButtonText; }
}
```

不要对整页 `forced-color-adjust:none`，那会夺走用户需要的高对比映射。

