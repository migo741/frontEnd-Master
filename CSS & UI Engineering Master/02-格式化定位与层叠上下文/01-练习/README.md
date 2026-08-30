# 练习：Sticky 与 Tooltip 事故法证

## 题 1（50 分钟）

修复一个后台页面：顶栏 sticky 失效、侧栏看似不能铺满、主内容出现两个垂直滚动条。只允许做最小结构和 CSS 修改。提交一张图标注 containing block、scroll container 和实际可用高度链。

禁止用任意固定 `height: 900px` 或 JS 测量视口。

## 题 2（50 分钟）

卡片内 tooltip 被裁切，modal 又被带 transform 的 header 压住，调高 z-index 无效。先解释每个 stacking context 和 clip ancestor，再分别给“局部浮层”与“全局模态”的正确实现。

验收：不使用六位数 z-index；建立有限层级 token；modal 使用 top layer；页面缩放和滚动后浮层仍正确。

