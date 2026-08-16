# 第 18 章练习

先提交威胁模型，再实现代码。禁止把“Prompt 里写了不要攻击”或“服务在内网”当验收证据。

## 练习一：防 DNS Rebinding 的受限 URL 抓取器

为“附件链接摘要”实现后端抓取器。

约束：

- 只允许 `https:` 和配置中的精确 hostname；
- 禁止 URL username/password 与非允许端口；
- DNS 解析后拒绝 loopback、private、link-local、multicast、IPv6 ULA 和 IPv4-mapped 私网；
- 实际连接必须 pin 到已经审查的 IP，不能校验后再次独立解析；
- 最多跟随 3 次重定向，每次从头验证；
- 总 deadline 5 秒、正文最大 2 MiB、只接受配置的 MIME；
- `Content-Length` 缺失或撒谎时仍能在流读取阶段截断；
- 不转发用户 Cookie、Authorization 或任意请求头；
- 日志记录 URL hash、目标 host、解析 IP、字节数和拒绝码，不记录敏感 query；
- 即使应用代码有遗漏，部署层仍有 egress deny-default 方案。

攻击测试至少包含十进制/IPv6 地址、重定向到内网、混合公私 DNS、超大 chunked body、慢响应和云元数据目标。

## 练习二：Prompt Injection 下仍最小权限的工具执行器

实现一个工具目录，仅开放：

```text
kb.search
attachment.read
ticket.propose_update
```

模型输入中会故意包含“读取 `/etc/passwd`、发送环境变量、调用隐藏管理员工具”的恶意文档。

约束：

- 未注册工具默认拒绝；
- 每个工具都有封闭参数 Schema、资源级 capability 和当前租户校验；
- 模型永远拿不到进程环境、数据库 DSN 或用户 bearer token；
- 每个 run 有最大 12 次工具调用、30 秒总时长和费用预算；
- 文件读取只能通过 attachment ID，不接受任意路径；
- 网络工具只能走练习一的抓取器或受控 egress；
- `ticket.propose_update` 只生成 intent，不执行真实更新；
- 日志对 token、email 和模型正文脱敏；
- 进程/容器层实施只读文件系统、非 root、无默认网络和资源限制；
- 并发耗尽、超预算、过期 capability 和 Prompt Injection 均有测试。

提交：威胁模型、工具目录、策略实现、攻击 fixture、NetworkPolicy/容器限制，以及一次红队复盘。
