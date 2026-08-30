# 练习：用 trace 而不是感觉优化

## 题 1（90 分钟）

优化包含 5,000 个活动卡片和复杂 hover/filter 的页面。记录同设备同数据 5 次 trace，定位 style/layout/paint；使用 containment、`content-visibility`、DOM/selector 收敛中的必要组合。

验收：报告优化前后中位数、DOM 数、内存与回归；页面查找、键盘焦点和滚动位置仍正确。

## 题 2（75 分钟）

为 SaaS 首屏设计 CSS/字体/主题交付：消除 FOUC/FOIT、控制 render-blocking、避免 purge 误删动态状态、图片/字体不产生明显 CLS。给出 gzip 预算、waterfall 和失败回退。

