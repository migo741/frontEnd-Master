# 第 20 章答案

## 练习一答案：贯通 HTTP → DB → Queue → Python 的安全 Trace

Node 初始化应在加载业务模块前执行：

```ts
// observability.ts
import { NodeSDK } from "@opentelemetry/sdk-node";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-http";
import { getNodeAutoInstrumentations } from "@opentelemetry/auto-instrumentations-node";
import { resourceFromAttributes } from "@opentelemetry/resources";
import { ATTR_SERVICE_NAME, ATTR_SERVICE_VERSION } from "@opentelemetry/semantic-conventions";

export const telemetry = new NodeSDK({
  resource: resourceFromAttributes({
    [ATTR_SERVICE_NAME]: "backend-api",
    [ATTR_SERVICE_VERSION]: process.env.APP_VERSION ?? "dev",
  }),
  traceExporter: new OTLPTraceExporter({
    url: process.env.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT,
    timeoutMillis: 2_000,
  }),
  instrumentations: [getNodeAutoInstrumentations({
    "@opentelemetry/instrumentation-http": {
      headersToSpanAttributes: { client: { requestHeaders: [] }, server: { requestHeaders: [] } },
    },
  })],
});

await telemetry.start();
```

队列载荷只传播标准 trace carrier：

```ts
import {
  context,
  propagation,
  trace,
  SpanKind,
  SpanStatusCode,
  ROOT_CONTEXT,
} from "@opentelemetry/api";

const tracer = trace.getTracer("agent-jobs");

type Job = Readonly<{
  messageId: string;
  runId: string;
  tenantId: string;
  enqueuedAt: string;
  trace: Record<string, string>;
}>;

export async function enqueueRun(base: Omit<Job, "trace" | "enqueuedAt">) {
  return tracer.startActiveSpan("queue.publish agent.run", async (span) => {
    const carrier: Record<string, string> = {};
    propagation.inject(context.active(), carrier);
    try {
      await queue.publish({ ...base, enqueuedAt: new Date().toISOString(), trace: carrier });
    } finally {
      span.end();
    }
  });
}

export async function consumeRun(job: Job) {
  const extracted = propagation.extract(ROOT_CONTEXT, job.trace);
  return context.with(extracted, () =>
    tracer.startActiveSpan(
      "queue.process agent.run",
      { kind: SpanKind.CONSUMER },
      async (span) => {
        span.setAttribute("messaging.message.id", job.messageId);
        span.setAttribute("app.run.id", job.runId);
        span.setAttribute(
          "messaging.queue.wait_ms",
          Math.max(0, Date.now() - Date.parse(job.enqueuedAt)),
        );
        try {
          await processRun(job);
        } catch (error) {
          span.recordException(error as Error);
          span.setStatus({ code: SpanStatusCode.ERROR, message: classify(error) });
          throw error;
        } finally {
          span.end();
        }
      },
    ),
  );
}
```

Python 提取同一 carrier：

```py
from opentelemetry import context, propagate, trace
from opentelemetry.trace import SpanKind

tracer = trace.get_tracer("agent-worker")

def process_job(job: dict) -> None:
    parent = propagate.extract(carrier=job.get("trace", {}))
    token = context.attach(parent)
    try:
        with tracer.start_as_current_span(
            "agent.run",
            kind=SpanKind.CONSUMER,
            attributes={"app.run.id": job["runId"]},
        ):
            run_agent(job)
    finally:
        context.detach(token)
```

不要从 carrier 读取 tenant；`tenantId` 来自经过签名/持久化的 job，并在数据库层再次限定。

Pino 脱敏示例：

```ts
import pino from "pino";

export const logger = pino({
  redact: {
    paths: [
      "req.headers.authorization",
      "req.headers.cookie",
      "*.password",
      "*.token",
      "*.apiKey",
      "*.prompt",
      "*.toolArgs.secret",
    ],
    censor: "[REDACTED]",
  },
  mixin() {
    const span = trace.getActiveSpan()?.spanContext();
    return span ? { traceId: span.traceId, spanId: span.spanId } : {};
  },
});
```

测试将 canary secret 放入每个敏感字段，捕获序列化日志和 span exporter，断言输出中不存在 canary。Exporter 使用批量与有界队列；遥测失败只记内部诊断，不能阻塞业务或无限缓存。

## 练习二答案：Agent SLO、Burn-rate 告警与容量拐点

示例核心 SLO：28 天滚动窗口内，合法且未被用户取消的 run 中，**99% 在 60 秒内进入通过业务校验的成功终态**。

记录规则示意：

```promql
# 总合格 run
sum(rate(agent_runs_total{eligible="true"}[5m]))

# 不良 run：失败、超 60 秒或结果校验不通过
sum(rate(agent_runs_total{eligible="true",slo_good="false"}[5m]))

# 错误比例
sum(rate(agent_runs_total{eligible="true",slo_good="false"}[5m]))
/
sum(rate(agent_runs_total{eligible="true"}[5m]))
```

1% error budget 下，burn rate 是 `error_ratio / 0.01`。快速告警可要求 1 小时和 5 分钟窗口都超过 14.4；慢速告警可要求 6 小时和 30 分钟窗口都超过 6。阈值需按团队响应能力验证，不机械照抄。

低基数 histogram：

```text
agent_first_meaningful_event_seconds{model_family,outcome}
agent_run_duration_seconds{workflow,outcome}
agent_queue_wait_seconds{queue}
agent_cost_usd_total{model_family}
agent_runs_total{workflow,outcome,slo_good}
```

`runId/tenantId` 只出现在 trace/log，不作为 label。

k6 负载骨架：

```js
import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  scenarios: {
    ramp: {
      executor: "ramping-arrival-rate",
      startRate: 5,
      timeUnit: "1s",
      preAllocatedVUs: 50,
      maxVUs: 500,
      stages: [
        { target: 20, duration: "3m" },
        { target: 50, duration: "5m" },
        { target: 100, duration: "5m" },
        { target: 0, duration: "2m" },
      ],
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<500"],
  },
};

export default function () {
  const key = `${__VU}-${__ITER}`;
  const response = http.post(
    `${__ENV.BASE_URL}/api/runs`,
    JSON.stringify({ workflow: "ticket-triage", ticketId: randomTicket() }),
    {
      headers: {
        "content-type": "application/json",
        "idempotency-key": key,
        authorization: `Bearer ${__ENV.TEST_TOKEN}`,
      },
    },
  );
  check(response, { accepted: (r) => r.status === 202 });
  sleep(Math.random());
}
```

测试环境的 model adapter 用可配置延迟分布与错误率，不能让第三方配额决定结果。逐段记录：到达率、完成吞吐、p95、oldest queue age、DB pool wait、worker busy、event-loop p99 和每成功成本。

容量拐点定义示例：到达率从 50 增至 70/s 时完成吞吐停在 55/s，queue oldest age 持续上升且 worker 95% busy；则安全上限不能写 70/s。保留 30% 余量后可先定约 38/s，再通过增加 worker、批处理或降低模型时间重测。

验收：同一脚本、数据规模和 fake 延迟下保存优化前后报告；runbook 写清限流、暂停低优先级任务、切备用模型和回滚版本的条件。

常见错误：把 run ID 放 metric label、用平均延迟、只监控 HTTP 200、每 token 建 span、让遥测 exporter 阻塞请求、压测时模型延迟固定为零、把最大打爆值当安全容量。

复写任务：不看答案重写 trace 注入/提取、日志 redaction、核心 SLI 公式与 k6 阶段，并口述从告警到根因的诊断链。
