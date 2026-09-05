# 第 10 章练习：异步组件契约与发布级测试组合

> 两题不追求数量。题 1 要把 Vue scheduler、Promise 和 timer 分清；题 2 要把一个核心业务路径按风险放到恰当层级。

## 题 1：测试一个防抖自动保存编辑器（机制题）

### 背景

`TicketTitleEditor` 接收：

```ts
interface Props {
  ticketId: string
  initialTitle: string
  save: (input: {
    ticketId: string
    title: string
    signal: AbortSignal
  }) => Promise<{ title: string; version: number }>
  debounceMs?: number
}
```

用户输入停止 300ms 后保存。继续输入会取消旧 debounce；保存中再输入，旧请求即使晚到也不能覆盖新文本；切换 `ticketId` 要取消请求并重置；卸载要清 timer/request。UI 有 `未修改/等待保存/保存中/已保存/保存失败/冲突` 状态，错误可重试。

### 契约

完成组件或 composable，并给出高价值测试。必须覆盖：

1. 输入后 299ms 不保存，300ms 保存一次；
2. 连续输入只保存最新文本；
3. A 保存慢、继续输入 B，A 成功不覆盖 B；
4. A 失败不把 B 标为失败；
5. 真实错误可重试，AbortError 不展示；
6. prop `ticketId` 变化取消前一资源并恢复新初值；
7. unmount 后 timer/Persistence 不提交；
8. 正确区分何时推进 fake timer、何时 resolve deferred、何时等待 Vue DOM；
9. 状态提示有 `role=status/alert` 或合理 aria-live；
10. 测试不调用组件私有方法。

### 规模与限制

- 输入频率最高 20 次/秒；
- save p95 1 秒，可能忽略 AbortSignal；
- strict TypeScript；
- 使用 Vitest + VTU 或 Testing Library；
- 测试结束恢复 real timers、mocks；
- 不允许用固定 sleep；
- 不要求 snapshot。

### 失败语义

| 场景 | 期望 UI |
|---|---|
| debounce 中 | “等待保存” |
| 当前版本在途 | “保存中” |
| 旧请求成功 | 忽略，不改当前文本/状态 |
| 当前请求失败 | “保存失败”，保留文本，可重试 |
| 409 冲突 | “冲突”，保留本地与服务端版本 |
| route/prop 切换 | 旧 ticket 不得污染新 ticket |

### 验收

- [ ] 状态用 discriminated union；
- [ ] timer 与 request 各有清理；
- [ ] Abort + generation 双保险；
- [ ] 至少 8 个行为测试，断言用户可见契约；
- [ ] 至少一个 deferred 乱序测试；
- [ ] 没有 `wrapper.vm.privateMethod()`；
- [ ] 没有任意次数 `flushPromises()` 或 `waitForTimeout`；
- [ ] 解释 DOM 模拟器与真实浏览器的测试边界。

### 发散

- 如果要求离线可靠保存，内存 composable 还缺哪些协议？
- 多标签同时编辑怎样从最后写入升级为冲突/协作模型？

---

## 题 2：为“发布知识库文章”设计发布门禁（生产开放题）

### 背景

流程包含：深链进入编辑页、恢复会话、加载文章、编辑富文本、自动保存草稿、上传附件、预览、点击发布、处理 401 refresh/409 冲突，最终读者页可见。支持 SSR 读者页；编辑页需 `article:publish`。历史事故有权限闪屏、旧草稿覆盖、重复发布、hydrate mismatch 和 E2E flaky。

### 契约

提交一份风险驱动测试计划和最小实现样例：

1. 风险清单，按概率×影响×难发现排序；
2. static/unit/component/integration/E2E/SSR/visual/a11y 的用例矩阵；
3. 哪些依赖真实、哪些 mock，以及原因；
4. MSW handlers：成功、401、403、409、422、500、慢响应、schema 错；
5. 真实 Router + Pinia + API client 的集成测试工厂；
6. 3~5 条关键 Playwright E2E，不复制所有边界；
7. 每 worker 数据 seed/cleanup 方案；
8. SSR 并发隔离和 hydration 测试；
9. visual/a11y 的稳定环境与人工检查；
10. CI 分层、失败证据、flake owner/期限、coverage 使用方式。

### 规模与限制

- PR 快速门禁目标 8 分钟内；
- E2E 可 4 worker 并行；
- 不接真实第三方对象存储，使用本地 fake server/协议模拟；
- 至少一条 staging smoke 验证真实部署集成；
- 关键发布路径不能长期 quarantine；
- 不设置单纯全局“90% 覆盖率即通过”；
- 所有未匹配 MSW 请求必须报错。

### 失败语义

- 测试失败必须保留能定位的证据：route/release/requestId/trace（脱敏）；
- E2E retry 通过仍记录首次失败；
- visual 基线变化需人工批准，不自动覆盖；
- a11y 自动扫描通过不代表人工键盘/读屏完成；
- cleanup 失败不能吞掉原始测试失败，也不能删除其他 worker 数据。

### 验收

- [ ] 每个高风险点都映射到能捕获它的最低充分层；
- [ ] unit/component/E2E 没有重复穷举同一规则；
- [ ] 真实 Router/Pinia/API client 至少在集成层相遇；
- [ ] SSR 两个并发用户有隔离断言；
- [ ] E2E 不使用固定 sleep 和共享固定实体；
- [ ] Playwright locator 以 role/label 为主；
- [ ] fake timers/network handler 生命周期清理；
- [ ] flake 治理有 owner、issue、deadline 和复现证据。

### 发散

- 当 PR 只改 `ticket-domain` 时怎样基于依赖图选择测试？
- 怎样用 mutation testing 判断权限/发布状态机的测试是否真的有效？
