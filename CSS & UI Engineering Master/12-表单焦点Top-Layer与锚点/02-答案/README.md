# 答案与复盘

## 题 1

```css
.control {
  min-block-size: 2.75rem;
  border: 1px solid var(--control-border);
  font: inherit;
}
.control:focus-visible {
  outline: 3px solid var(--focus-ring);
  outline-offset: 2px;
}
.field:has(:user-invalid) { --control-border: var(--danger); }
input:disabled { cursor: not-allowed; }
@media (forced-colors: active) {
  .control:focus-visible { outline-color: Highlight; }
}
```

错误元素用 `aria-describedby` 关联，服务端错误在提交后同样进入状态。loading 期间是否 disabled 是业务决策；若禁用会让焦点突然消失，应保持控件或把焦点移动到合理状态区。视觉测试必须补人工键盘/读屏验证。

## 题 2

基础版本先让 popover 在 top layer 中以可靠位置显示；Anchor 只是增强：

```css
.menu-trigger { anchor-name: --menu-trigger; }
.menu-popover {
  position: fixed;
  inset: auto;
}
@supports (position-anchor: --menu-trigger) {
  .menu-popover {
    position-anchor: --menu-trigger;
    inset-block-start: anchor(bottom);
    inset-inline-start: anchor(start);
    position-try-fallbacks: flip-block, flip-inline;
  }
}
```

Anchor 模块不同子能力的支持不一致，项目必须按实际 browser matrix 验证。fallback 可以是触发器下方的普通 popover 或小型 JS 定位；不能因为定位不完美而让菜单不可用。Dialog 使用 `showModal()`，不要仅加 open 属性模拟全部行为。

