# 运行

```bash
python test_solution.py
```

生产接入时把 `InMemoryExporter` 替换成 OpenTelemetry exporter，并为 run/model/tool/retrieval/approval 建 span。高基数或原始正文不可直接做 metric label。

