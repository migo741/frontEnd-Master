# 第 01 章练习

## 练习一：修复会串会话的状态管理器

下面设计在多会话中会泄漏消息：

```python
def new_session(messages=[]):
    return {"messages": messages, "meta": {"retries": 0}}
```

实现 `SessionStore`：

- create/get/append/update_meta/delete；
- 不同 session 不共享可变对象；调用者取得快照后不能偷偷修改 store；
- 区分 session 不存在、字段缺失、字段值为 None；
- 可序列化为 JSON 并恢复；
- 自定义异常保留 cause；至少 10 个 pytest 用例。

## 练习二：事件归一化器（高难）

把来自三个模型供应商的 raw dict 归一化为统一事件：text delta、tool call、usage、completed、failed。

要求：先只用本章语法实现；不能用 `is` 比字符串、不能吞未知事件、不能原地修改输入；处理缺字段、None、空字符串、bytes UTF-8 错误、未知 provider。写出你无法仅靠本章代码保证的事情，留到第 03 章解决。
