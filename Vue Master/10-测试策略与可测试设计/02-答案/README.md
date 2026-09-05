# 第 10 章答案：先证明并发语义，再证明 DOM

## 题 1 参考答案：自动保存是一台小型状态机

### 1. 状态与错误

```ts
type SaveState =
  | { status: 'clean'; confirmedVersion: number | null }
  | { status: 'queued' }
  | { status: 'saving'; submittedTitle: string }
  | { status: 'saved'; confirmedVersion: number }
  | { status: 'failed'; error: unknown }
  | {
      status: 'conflict'
      localTitle: string
      serverTitle: string
      serverVersion: number
    }

interface Conflict {
  kind: 'conflict'
  serverTitle: string
  serverVersion: number
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

function isConflict(error: unknown): error is Conflict {
  return typeof error === 'object' && error !== null &&
    'kind' in error && error.kind === 'conflict' &&
    'serverTitle' in error && typeof error.serverTitle === 'string' &&
    'serverVersion' in error && typeof error.serverVersion === 'number'
}
```

### 2. Composable 核心

```ts
import {
  onScopeDispose,
  readonly,
  ref,
  shallowRef,
  watch,
  type Ref,
} from 'vue'

interface AutosaveOptions {
  ticketId: Readonly<Ref<string>>
  initialTitle: Readonly<Ref<string>>
  debounceMs: Readonly<Ref<number>>
  save: (input: {
    ticketId: string
    title: string
    signal: AbortSignal
  }) => Promise<{ title: string; version: number }>
}

export function useTicketTitleAutosave(options: AutosaveOptions) {
  const title = ref(options.initialTitle.value)
  const state = shallowRef<SaveState>({ status: 'clean', confirmedVersion: null })

  let timer: ReturnType<typeof setTimeout> | null = null
  let controller: AbortController | null = null
  let generation = 0
  let suppressTextWatch = false
  let disposed = false
  let confirmedTitle = options.initialTitle.value

  function clearTimer() {
    if (timer !== null) clearTimeout(timer)
    timer = null
  }

  function invalidate(reason: string) {
    generation++
    clearTimer()
    controller?.abort(reason)
    controller = null
  }

  async function persist(mine: number, submittedTitle: string, ticketId: string) {
    if (disposed || mine !== generation) return
    clearTimer()
    const mineController = new AbortController()
    controller = mineController
    state.value = { status: 'saving', submittedTitle }

    try {
      const result = await options.save({
        ticketId,
        title: submittedTitle,
        signal: mineController.signal,
      })

      if (disposed || mine !== generation) return
      confirmedTitle = result.title
      suppressTextWatch = true
      title.value = result.title // 只有仍为当前 generation 才接受服务端规范化值
      suppressTextWatch = false
      state.value = { status: 'saved', confirmedVersion: result.version }
    } catch (error) {
      if (disposed || mine !== generation || isAbortError(error)) return

      if (isConflict(error)) {
        state.value = {
          status: 'conflict',
          localTitle: title.value,
          serverTitle: error.serverTitle,
          serverVersion: error.serverVersion,
        }
      } else {
        state.value = { status: 'failed', error }
      }
    } finally {
      if (mine === generation) controller = null
    }
  }

  function schedule() {
    invalidate('new edit')

    if (title.value === confirmedTitle) {
      state.value = { status: 'clean', confirmedVersion: null }
      return
    }

    const mine = generation
    const submittedTitle = title.value
    const ticketId = options.ticketId.value
    state.value = { status: 'queued' }
    timer = setTimeout(() => {
      void persist(mine, submittedTitle, ticketId)
    }, options.debounceMs.value)
  }

  const stopTitle = watch(title, () => {
    if (!suppressTextWatch) schedule()
  }, { flush: 'sync' })

  const stopTicket = watch(
    [options.ticketId, options.initialTitle],
    ([, nextInitial]) => {
      // initialTitle 更新若来自同 ticket 的后台刷新，产品可能选择冲突而不是覆盖；
      // 本题契约把 props 组合视作新基线。
      invalidate('ticket changed')
      confirmedTitle = nextInitial
      suppressTextWatch = true
      title.value = nextInitial
      suppressTextWatch = false
      state.value = { status: 'clean', confirmedVersion: null }
    },
    { flush: 'sync' },
  )

  async function retry(): Promise<void> {
    if (state.value.status !== 'failed') return
    invalidate('manual retry')
    const mine = generation
    await persist(mine, title.value, options.ticketId.value)
  }

  function acceptServerVersion() {
    if (state.value.status !== 'conflict') return
    const conflict = state.value
    invalidate('accept server')
    confirmedTitle = conflict.serverTitle
    suppressTextWatch = true
    title.value = conflict.serverTitle
    suppressTextWatch = false
    state.value = { status: 'saved', confirmedVersion: conflict.serverVersion }
  }

  onScopeDispose(() => {
    disposed = true
    invalidate('scope disposed')
    stopTitle()
    stopTicket()
  })

  return {
    title,
    state: readonly(state),
    retry,
    acceptServerVersion,
  }
}
```

两个关键点：

1. 每次编辑先 `generation++`，旧请求即使忽略 abort 也没有提交资格；
2. timer 回调捕获 `submittedTitle/ticketId/mine`，不会在 300ms 后读取到一组意外混合值。

同 ticket 的 `initialTitle` 后台变化是否覆盖本地草稿是产品决策。生产代码最好只在 `ticketId` 变化时重置，其他远端变化进入冲突协议；示例注释明确了简化契约。

### 3. 组件公开 DOM

```vue
<script setup lang="ts">
import { computed, toRef } from 'vue'

const props = withDefaults(defineProps<Props>(), { debounceMs: 300 })
const autosave = useTicketTitleAutosave({
  ticketId: toRef(props, 'ticketId'),
  initialTitle: toRef(props, 'initialTitle'),
  debounceMs: toRef(props, 'debounceMs'),
  save: props.save,
})

const message = computed(() => ({
  clean: '未修改',
  queued: '等待保存',
  saving: '保存中',
  saved: '已保存',
  failed: '保存失败',
  conflict: '存在编辑冲突',
}[autosave.state.value.status]))
</script>

<template>
  <label>
    标题
    <input v-model="autosave.title.value" aria-describedby="save-status" />
  </label>

  <p
    id="save-status"
    :role="autosave.state.value.status === 'failed' || autosave.state.value.status === 'conflict'
      ? 'alert' : 'status'"
  >
    {{ message }}
  </p>

  <button
    v-if="autosave.state.value.status === 'failed'"
    type="button"
    @click="autosave.retry"
  >
    重试保存
  </button>
</template>
```

在模板中 Vue 会自动解包顶层 ref，但这里 `autosave` 是普通对象，成员解包行为容易困惑。实际组件建议在 script 中解构 `const { title, state, retry } = ...`，模板写 `v-model="title"`、`state.status`；上面保留 `.value` 是为了突出 composable 类型，却可能不是最惯用的模板写法。生产答案应采用解构版本：

```ts
const { title, state, retry, acceptServerVersion } = useTicketTitleAutosave(/*...*/)
```

```vue
<input v-model="title" aria-describedby="save-status" />
<p id="save-status" :role="state.status === 'failed' ? 'alert' : 'status">
  {{ message }}
</p>
<button v-if="state.status === 'failed'" @click="retry">重试保存</button>
```

### 4. 测试工具

```ts
function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((ok, fail) => {
    resolve = ok
    reject = fail
  })
  return { promise, resolve, reject }
}

async function setTitle(wrapper: VueWrapper, value: string) {
  await wrapper.get('input[aria-describedby="save-status"]').setValue(value)
}
```

### 5. 防抖测试

```ts
describe('TicketTitleEditor', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('299ms 不保存，300ms 保存一次', async () => {
    const save = vi.fn().mockResolvedValue({ title: 'Vue 3', version: 2 })
    const wrapper = mount(TicketTitleEditor, {
      props: { ticketId: 'T1', initialTitle: 'Old', save, debounceMs: 300 },
    })

    await setTitle(wrapper, 'Vue 3')
    expect(wrapper.get('[role="status"]').text()).toBe('等待保存')

    await vi.advanceTimersByTimeAsync(299)
    expect(save).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(1)
    expect(save).toHaveBeenCalledTimes(1)
    expect(save).toHaveBeenCalledWith(expect.objectContaining({
      ticketId: 'T1', title: 'Vue 3', signal: expect.any(AbortSignal),
    }))
    await flushPromises()
    expect(wrapper.get('[role="status"]').text()).toBe('已保存')
  })

  it('连续输入只提交最后值', async () => {
    const save = vi.fn().mockResolvedValue({ title: 'ABC', version: 2 })
    const wrapper = mountEditor(save)

    await setTitle(wrapper, 'A')
    await vi.advanceTimersByTimeAsync(100)
    await setTitle(wrapper, 'AB')
    await vi.advanceTimersByTimeAsync(100)
    await setTitle(wrapper, 'ABC')
    await vi.advanceTimersByTimeAsync(300)

    expect(save).toHaveBeenCalledTimes(1)
    expect(save.mock.calls[0][0].title).toBe('ABC')
  })
})
```

这里 `advanceTimersByTimeAsync` 推进 debounce timer 及其 Promise continuation；`flushPromises` 只在 mock 已 resolve 后用于推进结果。没有 sleep。

### 6. 乱序测试

```ts
it('旧 A 成功不覆盖继续输入的 B', async () => {
  const a = deferred<{ title: string; version: number }>()
  const b = deferred<{ title: string; version: number }>()
  const save = vi.fn()
    .mockReturnValueOnce(a.promise)
    .mockReturnValueOnce(b.promise)
  const wrapper = mountEditor(save)

  await setTitle(wrapper, 'A')
  await vi.advanceTimersByTimeAsync(300)
  expect(wrapper.get('[role="status"]').text()).toBe('保存中')

  await setTitle(wrapper, 'B') // abort A + generation 增加
  a.resolve({ title: 'A-normalized', version: 2 })
  await flushPromises()
  expect((wrapper.get('input').element as HTMLInputElement).value).toBe('B')
  expect(wrapper.get('[role="status"]').text()).toBe('等待保存')

  await vi.advanceTimersByTimeAsync(300)
  b.resolve({ title: 'B', version: 3 })
  await flushPromises()
  expect(wrapper.get('[role="status"]').text()).toBe('已保存')
})

it('旧 A 失败不把 B 标失败', async () => {
  const a = deferred<{ title: string; version: number }>()
  const save = vi.fn()
    .mockReturnValueOnce(a.promise)
    .mockResolvedValueOnce({ title: 'B', version: 3 })
  const wrapper = mountEditor(save)

  await setTitle(wrapper, 'A')
  await vi.advanceTimersByTimeAsync(300)
  await setTitle(wrapper, 'B')
  a.reject(new Error('late A failure'))
  await flushPromises()

  expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  expect(wrapper.get('[role="status"]').text()).toBe('等待保存')
})
```

### 7. 其余高价值测试

```ts
it('当前保存真实失败显示 alert，点击重试立即保存当前文本')
it('AbortError 不出现用户错误')
it('409 显示本地与服务端版本并允许选择')
it('ticketId 切换 abort 旧请求并显示新 initialTitle')
it('unmount 清 timer，推进时钟后不调用 save')
it('unmount 后忽略不支持 abort 的晚结果')
it('输入改回 confirmedTitle 取消排队并显示未修改')
```

对 prop 切换应捕获传给 save 的 signal 并断言 `aborted === true`，再 resolve 旧 deferred，确认新 input/状态不变。

### 8. 什么留给真实浏览器

本题输入、状态和 timer 在 DOM 模拟器足够。以下留给 Playwright：实际 IME composition 行为、浏览器 tab/focus、页面切换 `beforeunload`、离线/恢复、跨 Tab、真实 network abort timing、视觉位置和屏幕阅读器体验。

### 9. 生产扩展

离线可靠保存还需要持久 outbox、幂等键、重放、schema/version、容量、加密/隐私和多 Tab 协调。多用户/多 Tab 编辑需要 server version、三方合并或 CRDT/OT；generation 只保证单页面实例内 latest-wins。

### 10. 常见错误

- 只清 debounce timer，不使在途请求失效；
- Abort 后认为旧 Promise 必不 resolve；
- `await nextTick()` 后断言网络完成；
- fake timer 下用 sleep；
- 测 `wrapper.vm.saveNow()`，绕过用户契约；
- 把 `isSaving/isSaved/hasError` 做三个可矛盾布尔值。

---

## 题 2 参考答案：从事故后果反推测试组合

### 1. 风险排序

| 优先级 | 风险 | 为什么高 | 最低充分层 |
|---|---|---|---|
| P0 | 无权限用户看到/发布文章 | 安全与声誉 | policy unit + Router/API integration + E2E |
| P0 | 重试造成重复发布 | 数据不可逆 | idempotency integration + E2E smoke |
| P0 | 旧草稿/旧响应覆盖新编辑 | 难复现、丢数据 | deterministic concurrency unit/component |
| P0 | SSR 跨用户泄漏 | 隐私事故 | 并发 SSR test |
| P1 | 401 refresh 风暴/死循环 | 大面积不可用 | API integration |
| P1 | 409 冲突丢本地内容 | 用户数据损失 | component/integration |
| P1 | 上传完成状态错误 | 大文件成本/数据 | upload state unit + integration |
| P1 | hydration mismatch | 首屏/交互问题 | SSR browser smoke |
| P2 | 富文本布局/键盘问题 | 可用性 | component + visual/a11y/browser |
| P2 | 错误文案/422 字段映射 | 转化影响 | component/MSW integration |

风险不是永久分数；事故、使用量、变更频率发生后更新。

### 2. 测试矩阵

#### Static

- route meta permission 必填规则；
- OpenAPI/codegen 后 git diff 为零；
- DTO/domain strict typecheck；
- feature 不反向依赖 app；
- no raw `v-html`（只允许 SafeRichText 封装）；
- bundle secret scan。

#### Unit

- publish 状态机合法/非法转移；
- query key、幂等键复用规则；
- URL/ID/parser；
- autosave generation、冲突合并；
- upload part scheduler/retry budget；
- sanitizer policy adapter 的固定恶意样本（同时依赖上游库测试）。

#### Component

- editor props/emits、dirty/queued/saving/error/conflict DOM；
- 发布按钮 permission/loading/double-click；
- 422 字段错误关联 label/input；
- Dialog Escape/focus 基础契约；
- SafeRichText 只接收 sanitized value 类型/封装。

#### Integration（真实 Vue + Router + Pinia + API client，MSW）

- 深链 session unknown -> `/me` -> 允许/登录/403；
- 4 个 401 singleflight，一次 refresh；
- publish 带固定 idempotency key，timeout 后查询状态；
- 409 保留 local/server/base；
- schema 错进入稳定 error boundary 并上报 request ID；
- route change abort + old response ignored；
- 上传 initialize/part/complete/verify 协议。

#### E2E（3~5 条）

1. 有权限作者深链进入、编辑、附件上传、预览、发布、读者页可见；
2. 无权限用户深链，敏感编辑 DOM 不出现，管理请求不发送，服务端直接 API 也 403；
3. 发布网络结果未知后刷新/查询，只产生一个发布版本；
4. 双人/版本冲突：本地文本保留，可选择合并后发布；
5. 会话过期恢复一次，回到当前草稿；若 staging 预算紧，把它作为 API integration + 一条 staging smoke。

#### SSR/Hydration

- 读者页 `renderToString` 含安全正文/metadata；
- A/B 用户并发 render store/query 不共享；
- 固定 locale/time/random 后浏览器 hydrate 无 warning；
- hydrate 后点赞/导航可交互；
- sanitizer 服务端/客户端输出一致。

#### Visual/a11y

- editor/preview/reader 的 light/dark、错误/长文/移动视口截图；
- axe 自动扫描；
- 键盘完成编辑、上传、冲突 dialog、发布；
- 焦点回归触发器、错误 announce；
- 200% zoom/reflow；关键版本人工读屏。

### 3. MSW 合同

```ts
export const handlers = [
  http.get('/api/me', () => HttpResponse.json(me)),
  http.get('/api/articles/:id', ({ params }) =>
    HttpResponse.json(articleDto({ id: String(params.id) }))),
  http.post('/api/articles/:id/publish', async ({ request }) => {
    const key = request.headers.get('idempotency-key')
    if (!key) return HttpResponse.json(problem('MISSING_KEY'), { status: 400 })
    return HttpResponse.json(publishedDto)
  }),
]

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
```

每个用例用 `server.use()` 覆盖：401 后 refresh、403、409 带 server version、422 fields、500、`delay('infinite')`/controlled delay、2xx 缺字段。不要把所有分支塞进一个根据全局可变计数器的巨型 handler；它会让并行和失败难解释。

### 4. 集成渲染工厂

```ts
async function renderEditorRoute(options: {
  route: string
  session?: SessionSeed
}) {
  const pinia = createPinia()
  const router = createRouter({
    history: createMemoryHistory(),
    routes: appTestRoutes,
  })
  const api = createApiClient({ baseUrl: 'http://localhost/api/' })
  const repositories = createRepositories(api)

  const app = render(App, {
    global: {
      plugins: [
        pinia,
        router,
        repositoriesPlugin(repositories),
      ],
    },
  })

  seedSession(pinia, options.session)
  await router.push(options.route)
  await router.isReady()
  return { ...app, router, pinia, api }
}
```

注意先 seed 还是先 push 取决于你是否要测试 session restore。工厂可提供显式模式，不要不透明地永远预登录。

### 5. Playwright 数据隔离

```ts
test('author publishes article', async ({ page, request }, testInfo) => {
  const namespace = `w${testInfo.workerIndex}-${crypto.randomUUID()}`
  const seed = await seedTenantAndAuthor(request, namespace)

  try {
    await loginAs(page, seed.author)
    await page.goto(`/articles/${seed.articleId}/edit`)
    await page.getByLabel('标题').fill('Vue 高级指南')
    await page.getByRole('button', { name: '发布' }).click()
    await expect(page.getByRole('status')).toHaveText('发布成功')
    await expect(page).toHaveURL(new RegExp(`/articles/${seed.articleId}$`))
  } finally {
    await cleanupNamespace(request, namespace).catch(error => {
      testInfo.attach('cleanup-error', {
        body: String(error), contentType: 'text/plain',
      })
    })
  }
})
```

cleanup 只按 namespace 删除本 worker 数据。若主体已失败，cleanup 错误附加诊断但不要覆盖原始错误；平台任务另行清理过期 namespace。

禁止 `waitForTimeout`。上传 fake server 应提供完成的可观察状态，Playwright 等 role/response。真实对象存储只保留少量受控 staging smoke。

### 6. SSR 隔离

```ts
it('A/B 并发渲染互不包含对方内容', async () => {
  const barrier = createBarrier(2)
  const render = (user: User) => renderRequest({
    user,
    url: `/articles/${user.privateArticleId}`,
    beforeRender: () => barrier.wait(),
  })

  const [a, b] = await Promise.all([render(userA), render(userB)])
  expect(a.html).toContain(userA.articleTitle)
  expect(a.html).not.toContain(userB.articleTitle)
  expect(b.html).toContain(userB.articleTitle)
  expect(a.serializedState).not.toContain(userB.id)
})
```

barrier 强迫两个请求生命周期重叠，才能捕获进程单例泄漏；顺序执行容易假绿。浏览器 smoke 监听 console hydration warning 并作为失败。

### 7. CI 分层

```text
PR（<=8 分钟）
  parallel: lint/type/architecture/codegen drift
  parallel: affected unit + component + integration
  build + bundle/secret budget
  3 条 mock-backed critical E2E（4 workers）

main
  full matrix + SSR/hydration + visual changed stories

nightly / pre-release
  full browsers + mutation subset + accessibility + flaky stress
  staging real deployment smoke
```

changed-test selection由依赖图决定；domain/shared/config/lockfile 变化扩大范围。定期完整运行检测 affected 配置漏边。

### 8. 失败证据和 flaky 规则

保存：Playwright trace、截图、console、脱敏 network、route name、request ID、release/build ID、worker/seed。默认可 retry 1 次用于收集信息，但报告展示首次失败和 flake 标记。

Quarantine 条件：非 P0/P1 主路径、已有 issue/owner/deadline、单独继续运行并可见。主发布路径 flaky 应阻断或立即修复，不能永久跳过。修复后 50~100 次随机顺序/并发 stress 验证。

### 9. Coverage 与 mutation

- 设合理底线防整块无测试，但不以 90% 作为成功定义；
- 查看 branch/state transition，尤其权限、publish/idempotency；
- mutation 示例：把 `canPublish` 条件取反、去掉 `idempotencyKey`、把 `incoming.version > current.version` 改成 `>=/无比较`，测试必须红；
- mutation 先跑纯 policy/state machine，控制成本；
- 对 UI 不做无差别 mutation 风暴。

### 10. 不重复的原则

“无标题不可发布”所有边界在 unit 穷举，组件只测一个错误呈现，E2E 不再遍历 20 种无效输入；E2E验证端到端关键价值。401 的 20 并发在 integration 精确控制，E2E只验证一次真实会话恢复。这样少而精，失败也能定位。

### 11. 错误方案

- 每层复制所有状态组合：慢、重复、维护成本高。
- E2E 全 mock Router/Pinia：失去端到端意义。
- 只测 staging：外部抖动让反馈慢且 flaky。
- visual 基线 CI 自动更新：回归被直接批准。
- axe 0 violation 宣称可访问完成：没有键盘/读屏证据。
- retry 后绿就删除失败记录：系统性竞态被掩盖。

### 复建要求

关掉答案，选自己产品的一条“不可失败路径”，写出：

1. 前五风险及故障后果；
2. 每个风险的最低充分测试层；
3. 三条 E2E 和它们**刻意不覆盖**的边界；
4. flaky 首次失败要保留的证据。

能解释为什么不多写一条测试，才真正掌握了“小而精”。
