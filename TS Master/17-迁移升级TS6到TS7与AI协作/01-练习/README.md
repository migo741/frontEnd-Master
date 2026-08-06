# 第 17 章练习

## 练习一：不停机迁移遗留订单包

订单包 35,000 行 JS/宽松 TS，CommonJS 与 ESM 混用，300 个隐式 any，接口响应直接断言，测试覆盖 42%，每周发布。目标在 8 周迁至 TS 6 strict，不能冻结功能。

要求：

- 按周给迁移阶段、质量门槛、owner 和回滚策略。
- 选择前 5 个迁移切面并说明风险排序。
- 设计 suppression/any 预算，防止“错误清零、风险不降”。
- 建立 TS 5.9→6.0 双 CI 与 consumer fixture。
- 为 TS 7 预览列出进入/退出标准。

## 练习二：审计 AI 生成的 API 客户端（高难）

```ts
async function get<T>(url: string): Promise<T> {
  const data = await fetch(url).then(r => r.json())
  return data as T
}

type DeepSafe<T> = T extends object
  ? { [K in keyof T]: DeepSafe<T[K]> }
  : NonNullable<T>

const user = await get<DeepSafe<User>>('/user')
```

AI 声称：“泛型 + DeepSafe 已确保后端一定返回无 null User”。

要求：

- 找出至少 10 个静态/运行时/协议问题。
- 重写为调用者不能任意声称输出类型的 API。
- 区分 HTTP、网络、协议、业务、取消错误。
- 加超时/取消、响应体大小或流式策略、Schema 与测试。
- 评估 DeepSafe 的语义和 checker 性能，而不只问是否能编译。
