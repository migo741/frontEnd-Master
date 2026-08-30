# 答案与复盘

## 题 1

```css
.prose { max-inline-size: 68ch; margin-inline: auto; line-height: 1.7; }
.prose h1 { font-size: clamp(2rem, 1.4rem + 2.4vw, 3.75rem); text-wrap: balance; }
.prose :where(pre, .table-wrap) { max-inline-size: 100%; overflow: auto; }
.prose a { overflow-wrap: anywhere; text-underline-offset: .15em; }
.nav-icon[aria-hidden="true"] { scale: var(--inline-direction, 1) 1; }
[dir="rtl"] { --inline-direction: -1; }
```

`ch` 是近似 measure，不保证中文正好 68 个字。检查段落实际视觉长度。代码保留内部 whitespace 时允许局部滚动；正文不能因一个 URL 让整页滚动。

## 题 2

```css
@font-face {
  font-family: "Brand Sans Fallback";
  src: local("Arial");
  size-adjust: 101.8%;
  ascent-override: 91%;
  descent-override: 23%;
  line-gap-override: 0%;
}
```

具体百分比必须由真实字体 metrics 计算，不能照抄。优先减少字体数量和字符集，preload 只给首屏真正使用的文件，否则抢占关键带宽。用相同缓存条件测试：首次无缓存、重复访问分别报告；只贴 Lighthouse 单次分数不合格。

