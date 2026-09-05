# 第 02 章练习：keyed diff 与异步工作区

## 练习 1：生成最少移动的 keyed patch 计划（机制题）

### 契约

实现纯函数，不操作真实 DOM：

```ts
export type PatchOp =
  | { type: 'patch'; key: string; oldIndex: number; newIndex: number }
  | { type: 'mount'; key: string; newIndex: number; beforeKey: string | null }
  | { type: 'unmount'; key: string; oldIndex: number }
  | { type: 'move'; key: string; newIndex: number; beforeKey: string | null }

export declare function planKeyedPatch(
  oldKeys: readonly string[],
  newKeys: readonly string[],
): readonly PatchOp[]
```

### 规则

1. 两个输入内部 key 必须唯一；重复时抛 `DuplicateKeyError`，错误含 key 和输入侧。
2. 新旧都有的 key 产生一次 `patch`；只在旧侧产生 `unmount`；只在新侧产生 `mount`。
3. 复用节点的移动数必须最少：对新顺序映射出的旧索引序列求 LIS，LIS 中节点不 move。
4. mount/move 从右向左规划，`beforeKey` 是操作时右侧已稳定的 key；最右为 null。
5. 不要求复制 Vue 的头尾优化，但总复杂度必须 O(n log n)，额外空间 O(n)。
6. 空输入、完全替换、头插、尾删、逆序都要正确。

### 验收样例

```ts
planKeyedPatch(['A', 'B', 'C', 'D'], ['B', 'E', 'D', 'A'])
```

必须：patch A/B/D；unmount C；mount E；对复用节点只 move 必要项，不能粗暴把全部 move。提交：实现、LIS 单测、至少 8 个 patch-plan 单测，以及一段手算说明。

### 发散

- 同样最少移动时，LIS 可能不唯一；测试为何不应绑定唯一操作序列？
- 真实 renderer 为什么还需比较 VNode type、处理 Fragment 和 transition？

---

## 练习 2：可缓存、可传送、可恢复的报表工作区（生产题）

### 场景

SaaS 报表页有三个重型页签：预览、设计器、运行记录。切换后保留各自草稿和滚动位置，最多缓存 2 个；设计器代码分包；全屏预览 Teleport 到 `#overlay-root`；首次加载显示 skeleton；chunk 加载失败可手动重试；页签隐藏时必须暂停轮询和快捷键，真正淘汰时释放资源。

### 组件契约

```ts
export type TabId = 'preview' | 'designer' | 'runs'

export interface WorkspaceTab {
  id: TabId
  reportId: string
}

// WorkspaceHost.vue
// props: modelValue: WorkspaceTab
// emits: update:modelValue(next: WorkspaceTab)
```

设计并实现以下文件的核心路径：

```text
WorkspaceHost.vue
AsyncPanelBoundary.vue
PreviewPanel.vue
DesignerPanel.async.ts
RunsPanel.vue
usePausablePolling.ts
```

### 行为与错误语义

1. 缓存身份为 `${tab.id}:${reportId}`，`KeepAlive :max="2"`；禁止 index/random key。
2. deactivated：暂停轮询、移除 window shortcut；activated：恢复且不得重复订阅；unmounted：最终 dispose。
3. async designer 最多自动重试 1 次；随后显示可访问的错误 UI，由用户点击重试。重试必须创建新 loader 代次。
4. fallback 延迟 150ms，避免快加载闪烁；超过 15s 视为失败。
5. Teleport 目标不存在时给出开发期明确错误；全屏关闭后焦点返回触发按钮。
6. Suspense 与错误边界职责分开；不得假设 fallback 能捕获 loader/渲染错误。
7. 组件卸载后任何 loader/轮询结果不得更新状态。

### 验收

- 切 preview→designer→preview，草稿与滚动状态保留；打开第三个 tab 后验证 LRU 淘汰带来全新实例。
- 连续激活/停用 20 次，任意时刻只有一个轮询计时器和一个 shortcut listener。
- loader 可控 Promise：验证 fallback 延迟、成功、超时、重试与最终错误。
- 全屏层实际位于 overlay root，逻辑 inject 仍可取到 Workspace context；Escape 关闭并恢复焦点。
- 使用 Vue Test Utils + Vitest，不真实 sleep；至少一条 Playwright 键盘/焦点流程。

### 交付物与发散

- 架构图、核心 SFC、测试、200 字以内“边界职责表”。
- 如果产品要求缓存 20 个设计器，你会如何估算内存并改变策略？
- 如果不接受 Suspense 的实验性，你会如何用显式状态机替换而不改业务面板？
