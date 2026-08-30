# 练习：极端用户环境压力测试

## 题 1（80 分钟）

修复一个鼠标可用但键盘/缩放失败的 Dashboard：导航 hover 才显示、焦点被裁、Grid order 与 DOM 不同、固定卡片高度剪字。通过 200% 和 400% zoom、仅增大文字、键盘全流程。

要求自动检查无 serious/critical，并附至少 8 项人工检查记录。

## 题 2（65 分钟）

让同一页面在 forced-colors、reduced-motion、无 hover 触摸设备和打印中保持任务可完成。状态不能只靠颜色，装饰不干扰，打印账单包含完整关键信息。

不得用一条 `* { animation:none !important }` 作为全部 reduced-motion 答案，需分类必要与非必要反馈。

