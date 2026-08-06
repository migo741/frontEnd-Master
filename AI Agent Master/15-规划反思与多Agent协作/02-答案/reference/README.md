# 运行

```bash
python test_solution.py
```

把 `search` fake 换成真实搜索 adapter 即可接入外部系统。生产实现还应并发执行 worker，但必须保留全局预算、deadline、ACL、结构化结果、冲突与失败状态。

