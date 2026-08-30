# 练习：并发 401 与富文本边界

## 题 1（75 分钟）

设计 fetch client：10 个并发请求同时 401，只刷新一次；成功后各重放一次；刷新失败只触发一次 logout；refresh endpoint 自己不能进入刷新循环；支持 AbortSignal；错误保留 requestId。写出核心代码和 5 个测试场景。

## 题 2（45 分钟）

OpsBoard 要显示用户提交的 Markdown、允许链接和代码块。给出威胁模型、数据流与防护点。至少处理 `javascript:` URL、内联 HTML、服务端存储内容、CSP 与管理员预览。不能只回答“用 v-html 很危险”。

