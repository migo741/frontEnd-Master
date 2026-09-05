# 第 03 章练习：状态证明与泛型组件契约

## 练习 1：把“用户编辑页”改造成可证明的状态机（机制题）

### 现有坏模型

```ts
interface State {
  loading: boolean
  saving: boolean
  user?: User
  draft?: Partial<User>
  error?: string
  dirty: boolean
}
```

### 任务契约

定义并实现：

```ts
export type UserEditorState = /* 判别联合 */
export type UserEditorEvent = /* 判别联合 */

export declare function transition(
  state: UserEditorState,
  event: UserEditorEvent,
): UserEditorState

export declare function parseUserDto(input: unknown): UserDto
export declare function toUser(dto: UserDto): User
```

### 合法业务语义

1. `idle → loading → ready | not-found | forbidden | load-error`。
2. 只有 ready 可 EDIT；draft 必须拥有完整 `name/email`，不能用 `Partial<User>`。
3. ready 分为 clean、dirty、saving、save-error；saving 保留 draft 和一个 `requestId`。
4. `SAVE_OK/SAVE_FAILED` 必须匹配当前 requestId；过期结果原样返回 state。
5. saving 期间允许继续 EDIT：新状态回到 dirty，旧保存结果随后不得覆盖新草稿。
6. 任何未知事件组合应在开发期抛明确错误；switch 必须穷尽。
7. `parseUserDto` 输入是 unknown，验证 id、name、email、`created_at`；转换后的 Domain 使用 `Date` 和 camelCase。

### 错误语义与限制

- 404 与 403 是独立状态，不得都压成 string error。
- 保存 409 是 `save-error` 且 `kind: 'conflict'`；其他错误为 `network | validation | unknown`。
- 每次 SAVE 由调用方给唯一 requestId；reducer 纯函数，不生成随机数、不请求网络。
- TypeScript strict，禁止 `any`、`as User`、非空断言。

### 验收与交付

- 类型、纯 reducer、schema/guard、至少 12 个迁移测试。
- 用 `assertNever` 证明 state 和 event 分支穷尽。
- 添加 4 个 `@ts-expect-error` 类型用例，证明 loading 没有 draft、clean 不能读 error、非法 email 字段类型、事件 payload 不可缺失。
- 发散：自动保存与手动保存是否应该共享同一 event？如何记录 reason 而不扩大非法状态？

---

## 练习 2：设计严格类型的通用 `EntityPicker`（生产题）

### 场景

组件库需要一个可选择任意领域实体的选择器。调用方传 `User[]` 后，model key、option slot、事件 payload 都必须自动推断为 User 相关类型；组件内部不能知道 `id/name` 固定字段。

### SFC 公共契约

```vue
<script setup lang="ts" generic="TItem, TKey extends PropertyKey">
// props:
// items: readonly TItem[]
// getKey(item): TKey
// getLabel(item): string
// disabled?: boolean
// model: TKey | null，required
// emits:
// select: [item: TItem, key: TKey]
// clear: []
// slots:
// option({ item, key, selected, active })
// empty({ query })
// expose: focus(): void, clear(): void
</script>
```

### 行为契约

1. 内部只保存 `query/open/activeKey`；选中真相来自 required model，禁止复制 prop 后 watch 同步。
2. key 用 `Object.is` 比较；重复 key 在开发期抛错。
3. 过滤后 model 对应项不存在时不擅自清空；显示“当前值不可见”，由调用方决定。
4. `clear()` 必须遵守 disabled；成功后更新 model 并 emit clear。`select` 只在真实选择发生时发。
5. option 子组件通过 `InjectionKey<PickerContext<TKey>>` 获得上下文；`usePickerContext()` 缺 provider 时 fail fast。
6. input template ref 必须正确处理未挂载；只 expose 两个命令。
7. 至少支持 10,000 items；computed 过滤，不 deep watch 整个数组。性能测试使用 profile 结论，不声称“类型能保证性能”。

### 类型验收

```vue
<EntityPicker
  v-model="selectedUserId"
  :items="users"
  :get-key="user => user.id"
  :get-label="user => user.name"
  @select="(user, id) => audit(user.email, id)"
>
  <template #option="{ item }">{{ item.email }}</template>
</EntityPicker>
```

`selectedUserId` 必须为 `string | null`；slot item 推断为 User；传 `Ref<number|null>`、访问 `item.unknown`、用错误 emit payload 都应类型失败。

### 运行时验收与交付

- 核心 SFC、context 模块、User 调用示例；`vue-tsc` 契约测试和 Vue Test Utils 行为测试。
- 键盘和 ARIA 的完整生产实现留到第 05 章；本题至少正确关联 label、listbox、option selected。
- 发散：如果 key 是对象，`PropertyKey` 约束会阻止它。为什么组件库通常应要求稳定 primitive key？
