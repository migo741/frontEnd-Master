# 第 09 章练习

## 练习一：可访问的注册表单

字段：email、password、confirmPassword、displayName、同意条款。

要求：

- 使用真实 form/label/name/autocomplete；密码可切换显示但不破坏值/焦点。
- 客户端做即时体验校验，服务端 action 重新执行 schema 与唯一性校验。
- 错误模型区分 fieldErrors/formError；错误与字段关联，提交失败聚焦错误 summary。
- pending 防重复且文案明确；网络失败保留非敏感输入。
- Email 已注册的提示不应在高安全场景泄露账号枚举，写出两种业务策略。
- React 19 使用 `useActionState/useFormStatus`；再写 React 18 兼容事件版的状态模型。
- 测试键盘提交、错误播报、服务器 422/429/500、重复点击。

## 练习二：乐观评论流（高难）

用户可快速发送多条评论，响应乱序；每条可失败、重试、删除。

要求：

- `useOptimistic` 或等价 reducer；每次用户意图有 clientId/idempotencyKey。
- 服务端成功返回 serverId/createdAt/version 后精确替换对应临时项。
- 响应乱序不改变用户看到的稳定排序；失败只标记自己的评论。
- 重试复用同一 idempotencyKey，避免服务器创建重复评论。
- 页面后台刷新得到服务器列表时，与 pending/failed 本地项合并去重。
- 发送期间切换频道，旧频道响应不能插入新频道。
- 测试 3 条乱序、第二条失败重试、频道切换、重复服务端响应。

回答：为什么“失败就恢复整个 previous comments 数组”在并发提交时是错的？

