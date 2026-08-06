# 运行

```bash
python test_solution.py
```

故障测试覆盖 checkpoint、乐观锁、lease 过期、zombie worker fencing、审批篡改/过期和操作重放。生产中的外部系统也必须使用 `operation_id` 做幂等，不能只在本地数据库去重。

