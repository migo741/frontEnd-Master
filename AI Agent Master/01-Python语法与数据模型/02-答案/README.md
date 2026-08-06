# 第 01 章参考答案

默认参数使用 `None`，内部创建新对象；store 保存自己的副本，读取返回防御性快照。不存在、缺失字段和字段值为 None 分开表达。恢复数据在进入 store 前校验版本与结构。

事件归一化不修改供应商输入，未知事件明确失败。仅凭普通 dict 仍不能得到完整运行时 Schema，这一层在第 03 章补齐。

## 可运行标准答案

- [源码](./reference/solution.py)
- [自动化测试](./reference/test_solution.py)
- [运行说明](./reference/README.md)

```bash
python "01-Python语法与数据模型/02-答案/reference/test_solution.py"
```

