# 第 09 章参考答案

## 练习一：Action 结果模型

```ts
type RegisterResult = {
  fieldErrors?: Partial<Record<'email' | 'password' | 'confirmPassword' | 'displayName' | 'terms', string>>
  formError?: string
  success?: true
}

const initialResult: RegisterResult = {}
```

```tsx
function RegisterForm() {
  const [result, action] = useActionState(register, initialResult)
  const summaryRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (result.fieldErrors || result.formError) summaryRef.current?.focus()
  }, [result])

  return (
    <form action={action} noValidate>
      <div ref={summaryRef} tabIndex={-1} role="alert">
        {result.formError}
      </div>
      <label htmlFor="email">邮箱</label>
      <input id="email" name="email" type="email" autoComplete="email"
        aria-invalid={Boolean(result.fieldErrors?.email)} aria-describedby="email-error" />
      <p id="email-error">{result.fieldErrors?.email}</p>
      {/* 其他字段 */}
      <SubmitButton />
    </form>
  )
}

function SubmitButton() {
  const {pending} = useFormStatus()
  return <button disabled={pending}>{pending ? '正在注册…' : '注册'}</button>
}
```

生产 action：解析 FormData → schema 校验 → 会话/风控/速率限制 → 幂等事务 → 返回安全错误。不能把数据库唯一约束异常原样返回。

账号枚举策略：普通社区可直接说“邮箱已注册”提升体验；金融/企业身份场景可统一返回“如果可以注册/登录，我们已发送说明”，并使响应时序尽量一致，实际政策由威胁模型决定。

React 18 用判别联合 reducer：idle/submitting/success/error，submit handler 创建 requestId/AbortController，服务端契约完全相同。

## 练习二：按意图投影

把权威 `baseComments` 和本地 `intents` 分开：

```ts
type Intent = {
  clientId: string
  channelId: string
  idempotencyKey: string
  body: string
  clientCreatedAt: number
  status: 'sending' | 'failed'
  server?: Comment
}
```

展示层：先对 base 以 serverId/idempotencyKey 去重，再加入尚未被确认的 intents；排序使用一次用户意图时确定的 `clientCreatedAt`，服务端时间只在稳定策略下校正，避免乱序跳动。

成功 action 携带 clientId，只替换该 intent；失败只标记该 clientId。频道切换时 query key 和 intent 都含 channelId，response reducer 先验证归属。重复响应因 idempotencyKey/serverId 去重。

重试复用原 idempotencyKey，但可以生成新的传输 requestId。服务器需在 user + operation scope 对 key 建唯一约束并返回原结果。

“恢复整个 previous 数组”把 A 开始时的全局快照当成 A 独有的变更。A 失败时，B/C 可能已成功或仍 pending，整数组回滚会抹掉它们。正确回滚单位是 A 自己的 intent/patch，并从权威 base + 剩余 intents 重算。

