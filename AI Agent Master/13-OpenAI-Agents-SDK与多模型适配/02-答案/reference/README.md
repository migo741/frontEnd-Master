# 运行

离线路由测试不调用模型：

```bash
python test_solution.py
```

真实 SDK 示例：

```bash
pip install "openai-agents>=0.4,<1"
OPENAI_API_KEY=你的密钥 python agents_sdk_integration.py
```

代码按 2026-08-04 的官方 Python SDK 用法编写，参考 [Quickstart](https://openai.github.io/openai-agents-python/quickstart/)、[Agents](https://openai.github.io/openai-agents-python/agents/) 和 [Running agents](https://openai.github.io/openai-agents-python/running_agents/)。不要把 tenant、权限或审批只放在 prompt 中。

