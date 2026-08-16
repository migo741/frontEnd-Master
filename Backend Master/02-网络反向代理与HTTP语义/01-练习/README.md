# 第 02 章练习

## 练习 1（经典必做）：可信代理请求上下文

实现纯函数 `resolveRequestContext(input)`，输出：

```ts
type RequestContext = {
  clientIp: string;
  scheme: "http" | "https";
  host: string;
};
```

输入包含 socket peer、socket 是否 TLS、`x-forwarded-for/proto/host` 和 `isTrustedProxy(ip)`。

不变量：

1. 直接 peer 不可信时，全部 forwarding headers 都忽略。
2. peer 可信时，把 peer 追加到转发链，从右向左跳过可信代理，取第一个不可信地址。
3. 最多接受 16 跳；拒绝空项、换行、非法 IP、非 `http/https` scheme 和非法 host。
4. host 必须属于配置 allowlist，不能用于开放重定向。
5. 测试覆盖直连伪造、多级可信代理、链中攻击者与 IPv4-mapped IPv6。

本题可把 CIDR 判断作为依赖注入；不要手写一个不完整的生产 CIDR 解析器。

## 练习 2（高难）：条件请求防止丢失更新

用 `node:http` 实现单资源 `/document`：

- `GET` 返回 JSON、强 ETag `"vN"` 与 `Cache-Control: private, no-cache`。
- `HEAD` 返回与 GET 相同的状态和表示头，但没有 body。
- GET/HEAD 的 `If-None-Match` 命中时返回 `304`，没有 body。
- `PUT` 必须带一个精确的 `If-Match`；缺失返回 `428`，过期返回 `412`。
- PUT 的版本比较与更新必须在同一原子临界区，成功后版本加一。
- 其余方法返回 `405` 与 `Allow: GET, HEAD, PUT`。
- 错误使用 `application/problem+json`，并限制 body 为 16 KiB。

验收：两个客户端读取同一 ETag 后同时 PUT，只能一个成功；失败客户端重新 GET 后才可更新。证明 `304`、HEAD 和 `204/304` 没有违规 body。

复写时把内存仓库替换成第 06 章的 PostgreSQL 条件更新，但 HTTP 契约保持不变。
