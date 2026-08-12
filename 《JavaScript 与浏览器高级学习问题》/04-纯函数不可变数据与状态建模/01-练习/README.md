# 第 04 章练习

不使用 Immer；先亲手建立结构共享和纯状态机的底层直觉。

## 练习 1（经典必做）：路径不可变更新

实现：

```js
const next = updateAtPath(root, path, updater);
```

契约：

1. root 只能由普通对象、数组和叶子值组成。
2. path 是字符串/非负整数数组，路径必须已经存在。
3. updater 恰好调用一次；若结果与旧叶子 `Object.is`，返回原 root。
4. 只复制根到叶子的路径，其他分支保持引用相等。
5. 不修改输入，保留数组稀疏位置。
6. 拒绝 `__proto__`、`prototype`、`constructor` 路径段。

测试深层对象、数组、根路径 `[]`、`NaN`、`0/-0` 和污染键。

## 练习 2（高难）：可重放自动保存状态机

实现纯函数：

```js
const { state: next, commands } = transition(state, event);
```

模型必须表达：当前文本与 editVersion、最后已保存版本、最多一个在途保存快照、错误。

事件至少包含：`EDITED`、`SAVE_REQUESTED`、`SAVE_SUCCEEDED`、`SAVE_FAILED`。

要求：

1. reducer 内不得读取时间、随机数或发请求；requestId 从事件传入。
2. SAVE_REQUESTED 只在 dirty 且无在途请求时产生一个 SAVE command。
3. 保存期间继续编辑，旧保存成功只能确认旧版本，不能把新编辑标为已保存。
4. 过期或未知 requestId 的成功/失败事件必须忽略并返回原状态。
5. 暴露 `isDirty`、`isSaving` 派生函数，不存重复布尔字段。
6. 用不少于 6 条事件序列测试，并写出至少 4 条始终成立的不变量。

这不是异步题；本题只建模，下一章才实现 command runner。
