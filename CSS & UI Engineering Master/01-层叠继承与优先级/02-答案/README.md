# 答案与复盘

## 题 1 推导方法

不要直接相加 specificity。先画候选表：selector 是否匹配 → origin/important → layer → specificity → scope proximity → order。前一步已分出胜负，后一步不再参与。例如 author normal 的未分层规则通常胜过 author normal 的任何 layer 规则，即使后者有 ID；行内 normal 又有独立的高优先位置，但仍会输给相同 origin 的 important。

Reduced motion 不是天然“更高级”。它只有在 media query 匹配后才进入候选，之后仍按普通 cascade 比较。可把用户偏好规则置于明确的 `overrides` layer，并避免组件用高权重阻挡它。

## 题 2 参考骨架

```css
@layer reset, vendor, base, components, utilities, overrides;

@import url("vendor.css") layer(vendor);

@layer reset {
  *, *::before, *::after { box-sizing: border-box; }
}

@layer components {
  :where(.field) { display: grid; gap: .375rem; }
  :where(.field__input) {
    border: 1px solid var(--field-border);
    font: inherit;
  }
  .field[data-invalid="true"] { --field-border: var(--color-danger); }
}

@layer overrides {
  .legacy-region .field__input { padding: revert-layer; }
}
```

`revert-layer` 让当前 layer 的声明退出，露出较早 layer 的值；它不是清空属性。迁移时先固定 layer 顺序，再降低基础 selector 权重，最后删除旧 important。若只是把所有旧 CSS 放进 `overrides`，虽然短期不破版，却没有建立可演进边界。

回归应覆盖 default/hover/focus/disabled/invalid/autofill，不只比较静态截图。

