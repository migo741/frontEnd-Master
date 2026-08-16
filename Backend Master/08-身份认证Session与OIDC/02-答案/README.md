# 第 08 章答案

以下实现展示不变量，不绑定某个 Web 框架。生产密码哈希应使用经过审计的 Argon2id 库；示例从“密码已验证”处开始。

## 练习一答案：Session 表与核心服务

```sql
CREATE TABLE app_user (
  id uuid PRIMARY KEY,
  credential_version bigint NOT NULL DEFAULT 0,
  disabled_at timestamptz
);

CREATE TABLE app_session (
  id uuid PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
  tenant_id uuid NOT NULL,
  secret_hash bytea NOT NULL UNIQUE CHECK (octet_length(secret_hash) = 32),
  csrf_hash bytea NOT NULL CHECK (octet_length(csrf_hash) = 32),
  credential_version bigint NOT NULL,
  auth_time timestamptz NOT NULL,
  last_seen_at timestamptz NOT NULL,
  idle_expires_at timestamptz NOT NULL,
  absolute_expires_at timestamptz NOT NULL,
  revoked_at timestamptz,
  replaced_by uuid REFERENCES app_session(id),
  CHECK (idle_expires_at <= absolute_expires_at)
);
CREATE INDEX app_session_user_active_idx
  ON app_session(user_id) WHERE revoked_at IS NULL;
```

核心使用 Node 24 内建密码学。数据库 adapter 必须把 `rotate` 放在一个事务里并锁定旧行。

```ts
import {createHash, randomBytes, randomUUID, timingSafeEqual} from 'node:crypto'

type Clock = {now(): Date}
type SessionRow = {
  id: string; userId: string; tenantId: string; secretHash: Buffer
  csrfHash: Buffer; credentialVersion: bigint; authTime: Date
  lastSeenAt: Date; idleExpiresAt: Date; absoluteExpiresAt: Date
  revokedAt: Date | null
}

interface SessionRepo {
  insert(row: SessionRow): Promise<void>
  findByHash(hash: Buffer): Promise<(SessionRow & {currentCredentialVersion: bigint; disabledAt: Date | null}) | null>
  touch(id: string, seen: Date, idleExpiry: Date): Promise<void>
  rotateLocked(oldHash: Buffer, next: SessionRow, now: Date): Promise<boolean>
  revokeByHash(hash: Buffer, now: Date): Promise<void>
  revokeAll(userId: string, now: Date): Promise<void>
}

const digest = (value: string) => createHash('sha256').update(value, 'utf8').digest()
const token = () => randomBytes(32).toString('base64url')
const addMs = (d: Date, ms: number) => new Date(d.getTime() + ms)

export class SessionService {
  constructor(private repo: SessionRepo, private clock: Clock) {}

  async create(userId: string, tenantId: string, version: bigint) {
    const now = this.clock.now(), secret = token(), csrf = token()
    const row: SessionRow = {
      id: randomUUID(), userId, tenantId, secretHash: digest(secret), csrfHash: digest(csrf),
      credentialVersion: version, authTime: now, lastSeenAt: now,
      idleExpiresAt: addMs(now, 30 * 60_000), absoluteExpiresAt: addMs(now, 12 * 60 * 60_000),
      revokedAt: null,
    }
    await this.repo.insert(row)
    return {secret, csrf, row}
  }

  async authenticate(secret: string | undefined) {
    if (!secret) return null
    const row = await this.repo.findByHash(digest(secret)), now = this.clock.now()
    if (!row || row.revokedAt || row.disabledAt) return null
    if (row.credentialVersion !== row.currentCredentialVersion) return null
    if (now >= row.idleExpiresAt || now >= row.absoluteExpiresAt) return null
    if (now.getTime() - row.lastSeenAt.getTime() >= 5 * 60_000) {
      const idle = new Date(Math.min(now.getTime() + 30 * 60_000, row.absoluteExpiresAt.getTime()))
      await this.repo.touch(row.id, now, idle)
    }
    return {userId: row.userId, tenantId: row.tenantId, sessionId: row.id, authTime: row.authTime}
  }

  async verifyCsrf(row: SessionRow, presented: string) {
    const actual = digest(presented)
    return actual.length === row.csrfHash.length && timingSafeEqual(actual, row.csrfHash)
  }

  async rotate(secret: string) {
    const old = await this.repo.findByHash(digest(secret)), now = this.clock.now()
    if (!old || old.revokedAt || old.disabledAt || old.credentialVersion !== old.currentCredentialVersion ||
        now >= old.idleExpiresAt || now >= old.absoluteExpiresAt) throw new Error('INVALID_SESSION')
    // 身份与租户只能来自旧 session，不能由请求参数指定。
    const next = await this.createDetached(old.userId, old.tenantId, old.currentCredentialVersion)
    if (!await this.repo.rotateLocked(digest(secret), next.row, this.clock.now())) {
      throw new Error('SESSION_ALREADY_ROTATED_OR_INVALID')
    }
    return {secret: next.secret, csrf: next.csrf}
  }

  private async createDetached(userId: string, tenantId: string, version: bigint) {
    const now = this.clock.now(), secret = token(), csrf = token()
    return {secret, csrf, row: {
      id: randomUUID(), userId, tenantId, secretHash: digest(secret), csrfHash: digest(csrf),
      credentialVersion: version, authTime: now, lastSeenAt: now,
      idleExpiresAt: addMs(now, 30 * 60_000), absoluteExpiresAt: addMs(now, 12 * 60 * 60_000), revokedAt: null,
    } satisfies SessionRow}
  }
}
```

`rotateLocked` 的 SQL 事务先 `SELECT ... FOR UPDATE`，重新确认旧行仍有效、credential version 未变且新旧 user/tenant 相同，再插入新行并更新旧行 `revoked_at/replaced_by`。不能先调用普通 `create` 落库，否则轮换失败会留下孤儿 Session。`touch` 也要用 `GREATEST(last_seen_at,$new)`，防止迟到请求把有效期倒退。

HTTP adapter 设置：

```ts
const cookie = `__Host-session=${secret}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=43200`
// 写请求同时要求 Origin 精确匹配，并从自定义 header 读取 CSRF token。
```

测试至少断言两个并发 `rotate(old)` 的结果为“一成功、一失败”，且 repo 中只有一条有效后继；logout 重复执行保持成功；错误日志只含内部 session row id。

## 练习二答案：一次性登录事务

```sql
CREATE TABLE oidc_login_attempt (
  state_hash bytea PRIMARY KEY,
  nonce text NOT NULL,
  verifier_ciphertext bytea NOT NULL,
  return_path text NOT NULL CHECK (return_path LIKE '/%' AND return_path NOT LIKE '//%'),
  expires_at timestamptz NOT NULL,
  consumed_at timestamptz
);
```

```ts
type Claims = {iss: string; aud: string | string[]; exp: number; iat: number; nonce: string; sub: string; azp?: string}
interface AttemptRepo {
  consume(stateHash: Buffer, now: Date): Promise<{nonce: string; verifier: string; returnPath: string} | null>
}
interface OidcProvider {
  exchange(code: string, verifier: string): Promise<{idToken: string}>
  verify(token: string, expected: {issuer: string; audience: string; algorithms: readonly string[]}): Promise<Claims>
}

export async function finishOidc(input: {
  state: string; code: string; now: Date; repo: AttemptRepo; provider: OidcProvider
  issuer: string; audience: string
}) {
  const attempt = await input.repo.consume(digest(input.state), input.now)
  if (!attempt) throw new Error('INVALID_OR_REPLAYED_LOGIN')
  const {idToken} = await input.provider.exchange(input.code, attempt.verifier)
  const claims = await input.provider.verify(idToken, {
    issuer: input.issuer, audience: input.audience, algorithms: ['RS256', 'ES256'],
  })
  const audiences = Array.isArray(claims.aud) ? claims.aud : [claims.aud]
  if (claims.iss !== input.issuer || !audiences.includes(input.audience)) throw new Error('BAD_TOKEN_CONTEXT')
  if (claims.exp * 1000 <= input.now.getTime() || claims.iat * 1000 > input.now.getTime() + 60_000) throw new Error('BAD_TOKEN_TIME')
  if (claims.nonce !== attempt.nonce) throw new Error('BAD_NONCE')
  if (audiences.length > 1 && claims.azp !== input.audience) throw new Error('BAD_AZP')
  return {subject: claims.sub, returnPath: attempt.returnPath}
}
```

`consume` 必须使用单条条件更新或锁：`UPDATE ... SET consumed_at=now() WHERE state_hash=$1 AND consumed_at IS NULL AND expires_at>now() RETURNING ...`。因此两个并发 callback 只有一个拿到事务。verifier 应加密保存或放短寿命受保护缓存，不能进入日志。

### 攻击与故障测试

- verifier fake 必须拒绝 `alg=none`、错误 issuer/audience/nonce/时间；
- `return_path` 测试 `https://evil`、`//evil`、反斜线与编码绕过；最好只保存解析后已批准的内部 route id；
- 未知 `kid` 最多触发一次受限 JWKS refresh，其余请求合并；
- token exchange 超时后 attempt 已消费，用户重新发起登录，而不是盲重试 callback；
- callback 成功而 Session 插入失败时让用户重新发起登录；不得把远程 token exchange 放进行锁事务，也不得重复消费授权码。

## 常见错误

- 把 OAuth access token 当 ID Token 使用；
- 只解码 JWT，不验证签名和上下文；
- 用 localStorage 保存长期 refresh token；
- 登出只清 Cookie、不撤销服务端记录；
- 在日志中打印 callback URL，间接泄漏 code/state。

## 复写验收

从空文件重写摘要查找、轮换事务和 OIDC 条件消费；用假时钟重放 idle/absolute expiry；并发测试必须可重复，而不是依赖 `setTimeout` 猜时序。
