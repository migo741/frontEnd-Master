# 第 21 章答案

## 练习一答案：不可变制品、兼容迁移与 Canary 发布

Node 多阶段镜像示例：

```dockerfile
# syntax=docker/dockerfile:1.7
FROM node:24.6.0-bookworm-slim AS deps
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN --mount=type=cache,id=pnpm,target=/pnpm/store \
    pnpm fetch --frozen-lockfile

FROM deps AS build
COPY . .
RUN --mount=type=cache,id=pnpm,target=/pnpm/store \
    pnpm install --offline --frozen-lockfile
RUN pnpm typecheck && pnpm test && pnpm build
RUN pnpm --filter backend-api deploy --prod /release

FROM node:24.6.0-bookworm-slim AS runtime
ENV NODE_ENV=production
WORKDIR /app
RUN apt-get update \
 && apt-get install -y --no-install-recommends tini ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY --from=build --chown=node:node /release/ ./
USER node
EXPOSE 3000
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["node", "dist/server.js"]
```

真实生产应把基础镜像 pin 到 digest，并由自动化更新机器人提交升级 PR。不要在 Dockerfile 写 `ARG SECRET`。

Kubernetes 部署关键部分：

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend-api
spec:
  replicas: 4
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0
      maxSurge: 1
  selector:
    matchLabels: { app: backend-api }
  template:
    metadata:
      labels: { app: backend-api }
    spec:
      terminationGracePeriodSeconds: 45
      serviceAccountName: backend-api
      containers:
        - name: api
          image: registry.example/backend-api@sha256:REPLACED_BY_PIPELINE
          ports:
            - { name: http, containerPort: 3000 }
          startupProbe:
            httpGet: { path: /health/startup, port: http }
            periodSeconds: 2
            failureThreshold: 30
          readinessProbe:
            httpGet: { path: /health/ready, port: http }
            periodSeconds: 5
            failureThreshold: 2
          livenessProbe:
            httpGet: { path: /health/live, port: http }
            periodSeconds: 10
            failureThreshold: 3
          lifecycle:
            preStop:
              exec: { command: ["/bin/sh", "-c", "sleep 5"] }
          resources:
            requests: { cpu: "250m", memory: "256Mi" }
            limits: { cpu: "1", memory: "768Mi" }
          securityContext:
            runAsNonRoot: true
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: { drop: ["ALL"] }
            seccompProfile: { type: RuntimeDefault }
```

`preStop sleep` 仅给负载均衡传播时间；应用本身仍必须捕获 SIGTERM，将 readiness 切为 false 并有界排空。

CI 骨架：

```yaml
name: release
on:
  push:
    branches: [main]
permissions:
  contents: read
  id-token: write
  packages: write
env:
  IMAGE: ghcr.io/${{ github.repository }}/backend-api
jobs:
  verify-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
      - run: pnpm install --frozen-lockfile
      - run: pnpm lint && pnpm typecheck && pnpm test
      - run: pnpm test:contracts && pnpm test:integration
      - name: Build once
        run: docker build --provenance=true --sbom=true -t "$IMAGE:$GITHUB_SHA" .
      - name: Scan
        run: trivy image --exit-code 1 --severity CRITICAL "$IMAGE:$GITHUB_SHA"
      - name: Push and record digest
        run: ./scripts/push-and-record-digest.sh "$IMAGE:$GITHUB_SHA"
  deploy:
    needs: verify-build
    environment: production
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Acquire short-lived cloud identity
        run: ./scripts/cloud-login-with-oidc.sh
      - name: Expand migration
        run: ./scripts/run-migration-job.sh expand
      - name: Canary exact digest
        run: ./scripts/progressive-rollout.sh --steps 5,25,100 --analyze-slo
```

Shell 脚本应校验 digest、namespace 和环境，禁止使用可变 `latest`。Canary 数据不足、run SLO 恶化、queue age 持续上升或成本异常都应暂停，而非默认成功。

迁移示例：先加 nullable `result_version`，新旧代码均可读；回填；新代码开始写；下一发布加约束；确认无旧实例后再删除旧字段。回滚应用时无需逆转已兼容的 expand。

## 练习二答案：满足 RTO/RPO 的跨组件灾难恢复演练

Runbook 的执行顺序模板：

```text
00 宣布事故、指定 incident commander、冻结非必要发布
01 隔离旧主库写入与旧区域任务消费者
02 选择恢复时间点并记录依据
03 在隔离网络恢复 PostgreSQL 全量备份 + WAL
04 运行 schema、租户、额度、审批、Outbox、审计校验
05 校验对象 manifest，隔离 hash 不符与孤儿对象
06 配置新 Redis，保持空库并由数据库/流量重建
07 启动消费者但暂不执行高风险外部工具
08 重放 Outbox；Inbox 去重；未知外部结果进入 reconciliation
09 运行 smoke、黄金 E2E、跨租户和余额校验
10 切换秘密/DNS/流量，监控 SLO 与重复副作用
11 宣布恢复；旧区域维持 fencing，禁止自动回切
12 记录实际 RTO/RPO、数据差异和后续行动
```

示例校验 SQL：

```sql
-- 找出没有租户或资源归属错误的业务记录
select count(*) from tickets t
left join tenants x on x.id = t.tenant_id
where x.id is null;

-- 终态 run 不应存在未完成的强制审批执行
select r.id, i.id
from agent_runs r
join tool_intents i on i.run_id = r.id and i.tenant_id = r.tenant_id
where r.status in ('succeeded','failed','cancelled')
  and i.status = 'executing';

-- 同一幂等键不应有多个业务结果
select tenant_id, idempotency_key, count(*)
from agent_runs
group by tenant_id, idempotency_key
having count(*) > 1;

-- 找出尚未发布的 durable intent
select count(*), min(created_at)
from outbox_events
where published_at is null;
```

恢复后不要直接清空并重建审计表；审计是调查权威。对象 manifest 至少包含 tenant、object key、version、size、hash 和数据库资源 ID。

外部工具结果分三类：确定未执行可安全重试；确定已执行则回填本地结果；未知则调用供应商查询/对账或人工判断。绝不能把“本地没记录”当“外部没发生”。

验收：计时从事故声明到用户黄金路径恢复；RPO 用实际缺失权威事务计算；执行恢复后重复 Outbox 测试；保存恢复数据库地址、备份 ID、WAL 点、校验结果和审批人，但脱敏秘密。

常见错误：每个 Pod 自动 migration、liveness 依赖数据库、使用 `latest`、回滚代码却不考虑消息/schema、从未恢复过备份、恢复后盲目重放外部副作用、旧区域恢复后形成双主。

复写任务：从空文件写 Docker runtime stage、三类 probe、expand/contract 时间线和 12 步 DR runbook，再用 10 分钟口述一次恢复决策。
