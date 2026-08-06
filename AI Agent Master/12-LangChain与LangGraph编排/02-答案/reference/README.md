# 可运行答案

- `solution.py`：零依赖显式状态图，可离线验证暂停、checkpoint 与幂等恢复。
- `langgraph_integration.py`：使用 `StateGraph`、`InMemorySaver` 和 `interrupt` 的真实 LangGraph 版本。

```bash
python test_solution.py
python langgraph_integration.py   # 需安装 frameworks extra
```

