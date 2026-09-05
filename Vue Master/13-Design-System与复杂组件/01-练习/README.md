# 第 13 章练习：可访问复杂组件与可演进系统

> 本章恰好两题。题目少，但每题都跨行为、视觉、版本与生产边界。

## 题 1：远程搜索 Combobox（Headless + Overlay + A11y）

### 背景

你要为设计系统实现单选 `AsyncCombobox<T>`。它会出现在普通表单和 Teleport 到 body 的 Dialog 中。搜索接口乱序返回；最多 50,000 个候选，单次返回 100 条；支持中文 IME；有 disabled option；组件可受控使用，并要提交 primitive id。

### 必须行为

- input 保持 DOM focus，popup 使用 listbox/option 语义；
- ArrowUp/Down/Home/End 移动 active option，跳过 disabled；
- Enter 提交，Escape 关闭并恢复查询，Tab 遵循明确策略；
- `aria-expanded/controls/activedescendant/autocomplete` 与状态同步；
- loading、empty、error、retry 可被读屏理解，但不可每个字符都骚扰 live region；
- IME composition 期间不错误触发提交/搜索；
- 新请求取消旧请求，旧响应不能覆盖新结果；
- popup 在 Dialog 中不被裁剪，Escape 只关闭顶层正确 overlay；
- SSR id 与首次 DOM 确定；组件卸载后无 timer/request/listener。

### 交付物

1. 状态、事件、transition 表；区分 query、active、committed value、open。
2. `AsyncCombobox<T>` 的 TypeScript public API，说明 identity、controlled/uncontrolled、slot contract 和 breaking 边界。
3. headless composable + 最小 styled template 的关键实现；允许省略浮层坐标算法，但要定义其接口。
4. 远程竞态、debounce、IME、focus/blur/outside click 和 OverlayManager 集成方案。
5. 至少 12 条测试，覆盖 unit、browser、a11y 与 SSR/hydration。
6. 性能边界：为什么单次 100 条可能不需虚拟化；若改为 10,000 本地项，需要补哪些能力？

### 发散追问

产品要求允许用户输入一个不存在的自由文本（creatable）。这会如何改变 value model、Enter/Escape、校验和无障碍提示？

## 题 2：DataGrid 与 Token v2 的无事故演进

### 背景

内部已有 30 个团队使用 `DataTable v1`。它接受 `rows: object[]`、`columns`，用数组下标作 key，选择状态由行对象引用表示，业务大量 deep selector 覆盖样式。新需求包括 100,000 行服务端数据、排序筛选、列宽、行选择、单元格编辑、键盘导航、暗色/高对比主题和品牌换肤。

同时你要把 token `--blue-600` 迁移成 `--color-action-primary`，并计划半年后发布 v2。

### 交付物

1. 先定义 v2 支持/不支持的场景与依赖方向；说明为何不是一次塞进所有功能。
2. 写 `DataGrid<Row>` 核心 API：稳定 row identity、column definition、server state、selection、focus/edit state、events/slots。
3. 为 100,000 行设计服务端 query + 虚拟窗口或分页方案；说明 table/grid 语义、键盘、读屏、打印、导出和降级。
4. 写 token 三层映射和旧 alias；定义 lint/codemod/dev warning 与删除时间线。
5. 制定 v1 → v2 双运行、consumer contract、canary、SemVer、回滚与遥测方案。
6. 给出测试矩阵：状态机、组件、浏览器、视觉、主题、SSR、消费者；每层说明能证明什么、不能证明什么。

### 约束

- 不能在浏览器一次加载 100,000 行再“分页”；
- 不能把业务权限逻辑放进 design-system 包；
- 不能承诺通过 `row === selectedRow` 保持跨请求选择；
- 不能在一次 minor 版本直接删除旧 token/DOM；
- 截图基线更新必须有人解释 diff。

### 发散追问

某核心业务依赖未公开 DOM selector，阻止 v2 发布。你会永久兼容、提供正式 slot/class hook、还是要求迁移？用影响面和长期成本写 ADR。
