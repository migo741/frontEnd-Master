# 运行

```bash
python test_solution.py
python generate_dataset.py
```

真实项目应把生产事故最小复现追加到版本化 JSONL，并在 CI 中比较基线。LLM judge 只用于难以确定性判断的维度，需盲化候选顺序并用人工样本校准。

