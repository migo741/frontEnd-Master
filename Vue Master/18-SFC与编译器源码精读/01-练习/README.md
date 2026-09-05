# 第 18 章练习：建立可复核的 SFC 编译档案

> 本章恰好两题。第一题追完整 SFC pipeline；第二题实现生产级只读诊断器。固定 `@vue/compiler-sfc` / `@vue/compiler-dom` 为 3.5.42，保存 lockfile，禁止用 main 分支结果回答。

## 练习 1：`TicketList.vue` 编译解剖

### 输入 SFC

```vue
<script setup lang="ts">
import { computed, ref } from 'vue'
import TicketRow from './TicketRow.vue'

interface Ticket {
  id: string
  title: string
  urgent: boolean
}

const props = withDefaults(defineProps<{
  tickets: readonly Ticket[]
  selectedId?: string
}>(), {
  selectedId: '',
})

const emit = defineEmits<{
  select: [id: string]
}>()

const query = defineModel<string>('query', { default: '' })
const input = ref<HTMLInputElement | null>(null)
const visible = computed(() =>
  props.tickets.filter(ticket => ticket.title.includes(query.value)),
)

defineExpose({ focus: () => input.value?.focus() })
</script>

<template>
  <section class="tickets" :class="{ empty: visible.length === 0 }">
    <label>
      Search
      <input ref="input" v-model="query" />
    </label>

    <p v-if="visible.length === 0">No tickets</p>
    <ul v-else>
      <TicketRow
        v-for="ticket in visible"
        :key="ticket.id"
        :ticket="ticket"
        :selected="ticket.id === selectedId"
        @select="emit('select', ticket.id)"
      />
    </ul>

    <footer>Stable footer</footer>
  </section>
</template>

<style scoped>
.tickets { container-type: inline-size; }
.tickets.empty { opacity: 0.7; }
.tickets :deep(.ticket-row) { min-block-size: 2.5rem; }
</style>
```

### 任务 A：SFC descriptor

调用 `parse(source, { filename, sourceMap: true })`，保存一个去除循环引用/非稳定字段的 `descriptor.json`，至少包含：

- filename；
- template/scriptSetup/style/custom block 数量；
- 每个 block 的 lang/scoped/module/attrs/loc；
- cssVars、slotted；
- parse errors 的 message/line/column。

不得直接 JSON.stringify 整个 compiler 对象。

### 任务 B：compileScript

调用 `compileScript(descriptor, { id: 'data-v-ticket-list' })`，保存：

- 生成 content；
- bindings metadata；
- imports 概要；
- props/emits/model/expose 分别如何出现在输出；
- `props`、`query`、`visible`、`TicketRow` 的 binding 类型；
- 哪些 TypeScript 类型被擦除；
- source map 是否能把一个生成位置映回原 SFC。

不要背 BindingTypes 数字，报告使用枚举名称。

### 任务 C：compileTemplate

把 `script.bindings` 作为 binding metadata，调用 template compiler。保存 `render.js` 与 `template-ast.json` 的精简版，并解释：

- helper 列表；
- components/directives；
- hoists/cached expressions；
- root、input、empty branch、v-for Fragment、TicketRow 的 patch flags；
- keyed Fragment 与 row key；
- static footer 是否提升；
- block/dynamicChildren 可能包含什么；
- `ticket` 为什么是 v-for scope binding，不是 `_ctx.ticket`。

再做两个变体并比较生成结果：

1. 删除 `:key="ticket.id"`；
2. 把显式 row props 改成 `v-bind="ticket"`。

说明行为/优化风险，不能只贴 diff。

### 任务 D：compileStyle

用相同 scope id 编译 style，保存 CSS/map/errors，解释普通 selector、`.empty`、`:deep()` 的结果。明确 scoped CSS 不是 Shadow DOM。

### 任务 E：运行时验证

使用真实 Vite/Vue fixture 或受控模块执行 generated render：

- query 变化更新列表；
- selectedId 只改变相关 row contract；
- row 重排保持 key identity；
- empty branch 切换；
- attrs/scope id 出现在预期 DOM；
- SSR（若做）与 client first render 一致。

### 发散问题

1. `cacheHandlers`、production/dev、SSR options 怎样改变输出？
2. 顶层 await 会怎样改变 compileScript output 与 component lifecycle？
3. HMR 如何判断只 rerender 还是必须 reload？
4. 大量 CSS `v-bind()` 对 runtime style 更新有什么影响？

### 交付物

- `compile-ticket-list.ts`；
- descriptor/script/template/style 精简 artifacts；
- 三组 generated output diff；
- runtime tests；
- public contract/internal artifact 对照表。

---

## 练习 2：SFC 安全与可维护性诊断器

### 场景

团队需要一个可在 CI 运行的小工具，先实现三条窄规则：

1. `security/no-raw-v-html`：发现 `v-html` 就报 error，除非表达式是显式 `sanitizeHtml(...)` 调用；
2. `correctness/require-v-for-key`：`v-for` 生成的 element/component 或 `<template v-for>` 缺少 key 时报告；
3. `ssr/no-nondeterministic-template`：template expression 直接出现 `Math.random()`、`Date.now()` 或 `window/document/localStorage` 时报告 warning。

这不是完整安全产品。目标是训练 AST、scope、loc、误报和升级边界。

### 接口

```ts
export interface SfcDiagnostic {
  filename: string
  rule:
    | 'security/no-raw-v-html'
    | 'correctness/require-v-for-key'
    | 'ssr/no-nondeterministic-template'
    | 'compiler/parse-error'
  severity: 'error' | 'warning'
  message: string
  line: number
  column: number
  source: string
}

export interface AuditOptions {
  ssr: boolean
  allowSanitizerNames?: readonly string[]
}

export function auditVueSfc(
  source: string,
  filename: string,
  options: AuditOptions,
): readonly SfcDiagnostic[]
```

### 约束

- 先用 compiler-sfc parse 找 template block；
- 再用 compiler-dom parse 生成 template AST；
- AST visitor 不能靠全文件 regex；
- compiler parse errors 必须保留；
- line/column 映射回整个 `.vue`，覆盖 template 不在第一行；
- 注释/custom block/style/script 中的字符串不得误报；
- `v-for` alias 作用域不能被 SSR rule 错判为 global；
- sanitizer allowlist 默认只有 `sanitizeHtml`，不接受任意 `safe*` 名称；
- 不为 v-html 自动修改源码；
- diagnostics 按 location + rule 稳定排序；
- malformed SFC 不能使进程 crash；
- 工具只扫描 `.vue` source，不加载/执行用户代码。

### 表达式分析

最低实现可对 directive/interpolation expression content 做窄 AST/词法检查，但要解释边界。优秀实现使用 Babel/ESTree parser 解析 Vue expression 并识别 member/call nodes，避免字符串字面量 `"window"` 误报。

不允许把任意包含 `sanitizeHtml` 文本的表达式放行：

```vue
<!-- 不应放行 -->
<div v-html="unsafe + 'sanitizeHtml'" />

<!-- 可放行 -->
<div v-html="sanitizeHtml(article.body)" />
```

### 最少 fixture

- 安全 sanitizer call；裸 `v-html="html"`；嵌套/命名空间 sanitizer；
- 注释和 script string 中的 `v-html`；
- element `v-for` 有/无 key；`template v-for` 有/无 key；
- key 错放在 child；
- `Math.random()`、`Date.now()`、window/localStorage；
- 字符串字面量与对象属性名不误报；
- multiline template 的准确 line/column；
- 无 template；
- SFC/template 语法错误；
- Windows newline；
- SSR false 时 nondeterministic rule 不报告。

### CI 与维护

提交：

- content hash cache 设计；
- 只扫 changed files 与全量 nightly 的取舍；
- compiler 版本 pin；
- golden diagnostics；
- false-positive suppression 格式与审计期限；
- 升级 Vue 后怎样区分 AST 漂移和规则 bug。

### 发散问题

1. 为什么这三条规则更适合 ESLint plugin，而不是 Vite transform？
2. `v-safe-html` custom directive 是否真的比 sanitizer call 安全？还缺什么？
3. SSR nondeterminism 通过 composable 间接发生时，template AST 为什么看不到？
4. 自动修复缺 key 时为什么不能生成 index key？

### 交付物

- `auditVueSfc.ts`；
- 至少 15 个 fixture tests；
- JSON 与人类可读 reporter；
- 误报/漏报文档；
- compiler 升级 ADR。
