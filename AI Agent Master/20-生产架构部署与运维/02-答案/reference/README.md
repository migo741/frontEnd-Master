# 运行

```bash
python test_solution.py
pip install "fastapi>=0.115,<1" "uvicorn[standard]>=0.30,<1"
uvicorn app:app --reload
```

也可用 `docker compose -f compose.yaml up --build` 启动本地拓扑。Compose 凭据只适用于本地练习；生产需要 secret manager、TLS、迁移任务、备份恢复、区域隔离、限流和 kill switch。

