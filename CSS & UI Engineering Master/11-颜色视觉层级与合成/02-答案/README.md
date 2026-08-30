# 答案与复盘

## 题 1

从固定 lightness/chroma 约束生成候选，再逐个落到真实背景验证。不要把同一个前景色假设为在 canvas、raised surface、selected surface 上都通过。disabled 状态不必追求正常文字对比，但仍需可辨认且不能只靠低 opacity；可结合 cursor、结构、文本和原生 disabled 语义。

```css
:root {
  --surface-1: oklch(99% .005 250);
  --surface-2: oklch(96% .008 250);
  --text-1: oklch(24% .02 250);
  --action: oklch(55% .18 255);
  --focus-ring: oklch(68% .17 250);
}
```

数值只是起点，需用对比工具和浏览器实际渲染验证。

## 题 2

每个系列同时分配 color + dash/marker/label；badge 使用图标或文字。打印 stylesheet 移除非必要背景，恢复可见 border：

```css
@media print, (forced-colors: active) {
  .chart-series { stroke: CanvasText; }
  .series-a { stroke-dasharray: none; }
  .series-b { stroke-dasharray: 6 3; }
  .status { border: 1px solid currentColor; }
}
```

`forced-color-adjust:none` 只用于确实必须保留且已验证的色样，不应用于整个图表；在系统配色下保持标签和线型更可靠。

