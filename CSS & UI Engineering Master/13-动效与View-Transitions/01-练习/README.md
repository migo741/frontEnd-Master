# 练习：可中断、可降级的状态动效

## 题 1（70 分钟）

实现 Button、Toast、Drawer、Dialog、Skeleton 五种状态动效。快速连续开关不得卡在半透明或错误位置；内容从一开始就可访问；reduced motion 下取消大位移但保留清晰状态反馈。

提交 Performance trace，说明哪些动画走 layout/paint/composite，不能只引用“transform 最快”。

## 题 2（75 分钟）

实现 SaaS 项目列表到详情的同文档 View Transition，并增加轻量阅读进度的 scroll-driven enhancement。前进、返回、快速导航、重复名称、异步内容都要测试；不支持新 API 时立即完成导航、内容默认可见。

