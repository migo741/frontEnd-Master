# 答案与复盘

## 题 1

```css
@layer reset, vendor, tokens, base, components, utilities, overrides;
@import url("element-plus.css") layer(vendor);
```

feature 只导入自己组件模块；tokens/base 可被所有 feature 消费但不能反向依赖。第三方 adapter 用公开变量/API 优先，其次在限定 root 下做低权重覆盖。`overrides` 只能存有 owner 和删除条件的暂时规则。

Vue Teleport 内容不在 scoped DOM 后代关系中；应让 Teleport component 自带样式，或由全局 components layer 提供，不能靠父组件 `:deep(body > ...)`。

## 题 2

```css
.status-badge {
  --badge-bg: var(--status-neutral-bg);
  --badge-fg: var(--status-neutral-fg);
  display: inline-flex;
  align-items: center;
  gap: .375em;
  background: var(--badge-bg);
  color: var(--badge-fg);
}
.status-badge[data-tone="danger"] {
  --badge-bg: var(--status-danger-bg);
  --badge-fg: var(--status-danger-fg);
}
```

公开 `--badge-bg` 代表允许消费者自定义；内部 gap/token 未必公开。删除 tone、改状态属性、改变 token 语义或 DOM part 名都可能是 breaking；纯内部 class hash 变化不是。契约文档要列状态矩阵和 fallback，而不是暴露全部实现。

