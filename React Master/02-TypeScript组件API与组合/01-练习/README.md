# 第 02 章练习

## 练习一：类型安全的 AsyncSelect

设计一个 `AsyncSelect<T>`，调用形式如下：

```tsx
<AsyncSelect
  items={users}
  getKey={user => user.id}
  getLabel={user => user.name}
  value={selectedUser}
  onValueChange={setSelectedUser}
  status={{kind: 'ready'}}
/>
```

要求：

1. `T` 从 `items` 推断；`getKey/getLabel/value/onValueChange` 都保持同一 T。
2. 受控与非受控互斥：受控需 `value + onValueChange`；非受控允许 `defaultValue`，不得同时传 `value`。
3. 状态使用判别联合：`idle | loading | ready | error`；error 必须包含 `message` 和 `retry`，其他状态不得传 retry。
4. 不用 `any`、非必要类型断言和索引 key。
5. 空列表、loading、error 有可访问的状态提示；选择控件有 label。
6. 写至少 4 个类型测试：两个应通过、两个用 `@ts-expect-error` 验证非法 API。

高难点：考虑 `T | null` 的“未选择”语义；不要用 `undefined` 同时表示非受控和未选择，避免模式判断歧义。

## 练习二：组合式 Modal API

设计以下 API 的类型和最小行为：

```tsx
<Modal.Root open={open} onOpenChange={setOpen}>
  <Modal.Trigger>删除项目</Modal.Trigger>
  <Modal.Content aria-label="确认删除">
    <Modal.Title>不可撤销</Modal.Title>
    <Modal.Description>项目及其数据将被删除。</Modal.Description>
    <Modal.Close>取消</Modal.Close>
    <button onClick={remove}>确认</button>
  </Modal.Content>
</Modal.Root>
```

要求：

- Root 支持严格受控/非受控两种模式。
- 子组件脱离 Root 使用时抛出清晰错误。
- Trigger/Close 能把事件与内部行为组合；用户 handler `preventDefault()` 时不继续默认开关。
- Content 用 Portal；初步完成 `role="dialog"`、`aria-modal`、Escape 关闭、关闭后焦点回 Trigger。
- 不允许通过十几个布尔 prop 配置所有布局。

说明：生产中应优先采用经过审计的 headless primitive；此题用于理解 API、所有权和焦点责任，不鼓励重复造完整无障碍对话框。

## 验收问题

1. 为什么 `ReactNode` 不适合要求“恰好一个可 clone 元素”的参数？
2. 为什么把 `onChange(event)` 暴露到业务层会增加耦合？
3. 什么时候不该做多态 `as`？

