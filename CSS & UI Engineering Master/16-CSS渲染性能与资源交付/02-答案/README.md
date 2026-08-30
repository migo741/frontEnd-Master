# 答案与复盘

## 题 1

先录制基线，不要一上来加 contain。若长任务来自 JS 排序，CSS 优化不能解决。确认离屏卡片耗费后：

```css
.activity-card {
  content-visibility: auto;
  contain-intrinsic-size: auto 12rem;
}
```

在现代支持环境中增强，验证滚动、Ctrl+F、锚点和焦点。稳定的 intrinsic estimate 能降低滚动跳动；真实尺寸访问后 `auto` 可记住尺寸。若每张卡高差巨大，单一 estimate 仍会抖动。大型列表最终可能需要虚拟化，但那属于 JS/组件层取舍。

## 题 2

策略示例：首屏 shell/tokens/base 随文档或单一关键 stylesheet；路由组件 CSS 与代码一起分割；主题属性在首 paint 前确定；字体只 preload 首屏使用的一个 subset，并提供指标匹配 fallback；所有媒体有尺寸。

预算不是通用答案，可从“关键 CSS ≤ 20KB gzip、首屏总 CSS ≤ 60KB gzip、字体首屏 ≤ 100KB”作为实验起点，再由真实产品调整。CI 检查 bundle diff，预发跑 Web Vitals；不能为了预算把可访问状态样式 purge 掉。动态 class 使用明确映射：

```ts
const tones = { danger: 'text-danger', success: 'text-success' } as const
```

不要拼接无法静态发现的 `text-${tone}`。

