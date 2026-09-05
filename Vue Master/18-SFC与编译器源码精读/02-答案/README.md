# 第 18 章答案：从 SFC Artifact 到可维护诊断器

> 参考答案固定 `@vue/compiler-sfc@3.5.42`、`@vue/compiler-dom@3.5.42`。生成代码必须以你本机保存的 artifact 为准；本答案解释稳定结构，不把某段近似输出伪装成所有 options 下的逐字符快照。

## 练习 1 参考答案：`TicketList.vue` 编译解剖

### 1. 建立可重跑脚本

依赖应直接声明并锁版本，不依赖 Vite 的传递依赖：

```json
{
  "devDependencies": {
    "@vue/compiler-dom": "3.5.42",
    "@vue/compiler-sfc": "3.5.42",
    "typescript": "^5.9.0",
    "vitest": "^3.0.0"
  }
}
```

版本示意中的 TypeScript/Vitest 范围应按项目支持矩阵锁定；关键是 Vue runtime 与 compiler-sfc 使用同一 3.5.42 线。

核心脚本：

```ts
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import {
  compileScript,
  compileStyle,
  compileTemplate,
  parse,
  type SFCBlock,
  type SFCDescriptor,
} from '@vue/compiler-sfc'

interface StableBlock {
  type: string
  lang: string | null
  attrs: Record<string, string | true>
  start: { line: number; column: number; offset: number }
  end: { line: number; column: number; offset: number }
}

function stableBlock(block: SFCBlock | null): StableBlock | null {
  if (!block) return null
  return {
    type: block.type,
    lang: block.lang ?? null,
    attrs: { ...block.attrs },
    start: { ...block.loc.start },
    end: { ...block.loc.end },
  }
}

function stableDescriptor(descriptor: SFCDescriptor) {
  return {
    filename: descriptor.filename,
    template: stableBlock(descriptor.template),
    script: stableBlock(descriptor.script),
    scriptSetup: stableBlock(descriptor.scriptSetup),
    styles: descriptor.styles.map(block => ({
      ...stableBlock(block),
      scoped: Boolean(block.scoped),
      module: block.module ?? false,
    })),
    customBlocks: descriptor.customBlocks.map(stableBlock),
    cssVars: [...descriptor.cssVars],
    slotted: descriptor.slotted,
  }
}

async function save(path: string, value: string): Promise<void> {
  await mkdir(dirname(path), { recursive: true })
  await writeFile(path, value, 'utf8')
}

async function main(): Promise<void> {
  const filename = resolve('fixtures/TicketList.vue')
  const outputDir = resolve('artifacts/ticket-list')
  const source = await readFile(filename, 'utf8')
  const parsed = parse(source, { filename, sourceMap: true })

  await save(
    resolve(outputDir, 'descriptor.json'),
    JSON.stringify(
      {
        descriptor: stableDescriptor(parsed.descriptor),
        errors: parsed.errors.map(error => String(error)),
      },
      null,
      2,
    ),
  )

  if (parsed.errors.length > 0) {
    throw new Error(`SFC parse failed with ${parsed.errors.length} errors`)
  }

  const { descriptor } = parsed
  if (!descriptor.scriptSetup || !descriptor.template) {
    throw new Error('Fixture requires <script setup> and <template>')
  }

  const id = 'data-v-ticket-list'
  const script = compileScript(descriptor, {
    id,
    inlineTemplate: false,
  })

  await save(resolve(outputDir, 'script.ts'), script.content)
  await save(
    resolve(outputDir, 'bindings.json'),
    JSON.stringify(script.bindings, null, 2),
  )

  const template = compileTemplate({
    source: descriptor.template.content,
    filename,
    id,
    scoped: descriptor.styles.some(style => style.scoped),
    slotted: descriptor.slotted,
    isProd: false,
    compilerOptions: {
      bindingMetadata: script.bindings,
      hoistStatic: true,
      cacheHandlers: true,
    },
  })

  if (template.errors.length > 0) {
    throw new Error(
      `Template compile failed: ${template.errors.map(String).join('\n')}`,
    )
  }

  await save(resolve(outputDir, 'render.js'), template.code)
  await save(
    resolve(outputDir, 'template-summary.json'),
    JSON.stringify(summarizeTemplateAst(template.ast), null, 2),
  )

  for (const [index, styleBlock] of descriptor.styles.entries()) {
    const style = compileStyle({
      source: styleBlock.content,
      filename,
      id,
      scoped: Boolean(styleBlock.scoped),
      trim: true,
    })
    if (style.errors.length > 0) {
      throw new Error(`Style ${index} failed: ${style.errors.map(String).join('\n')}`)
    }
    await save(resolve(outputDir, `style-${index}.css`), style.code)
    await save(
      resolve(outputDir, `style-${index}.map.json`),
      JSON.stringify(style.map ?? null, null, 2),
    )
  }
}

void main()
```

`summarizeTemplateAst` 必须自己选择稳定字段，例如 node type/tag/loc/patchFlag，不应把整个带内部引用的 AST 直接 JSON 化。脚本中的 Node 版本 API 与项目 module mode 也要由 tsconfig 验证。

### 2. Descriptor 结论

本 fixture 应得到：

```text
template: 1
script: 0
scriptSetup: 1, lang=ts
styles: 1, scoped=true
customBlocks: 0
```

Block loc 指向内部 content，而非开标签本身。精简 artifact 应保留 start/end offset，后续 template local loc 才能映射回 SFC whole-file offset。

不要保存 `descriptor.source` 的完整副本到每个 JSON；它重复且可能包含敏感 fixture。artifact 可保存 content hash 和受审查的小 fixture。

### 3. compileScript 结论

类型-only 内容 `interface Ticket` 会从运行时 JavaScript 擦除，但可能参与 props 类型生成。宏的概念结果：

| 源宏/绑定 | 编译结果 |
| --- | --- |
| `defineProps` + `withDefaults` | 组件 props runtime metadata + setup 中的 props alias |
| `defineEmits` | emits option + setup emit binding |
| `defineModel('query')` | query prop、`update:query` emit 与 `useModel` 类生成逻辑 |
| `defineExpose` | setup context expose call |
| `TicketRow` import | template 可直接引用的 setup const/import binding |
| `query` | setup ref/model ref binding |
| `visible` | computed ref，template 自动 unwrap |

具体 `BindingTypes` 名称以 `bindings.json` 为准。通常：

```text
tickets / selectedId → PROPS
query / input / visible → SETUP_REF（细节以 artifact 为准）
TicketRow / imported APIs → SETUP_CONST 或 imported binding metadata
props / emit → SETUP_CONST 类别
```

不要把这些名称写入业务逻辑；它们用于 compiler 协作。

`selectedId` default 的生成方式可能受 compiler 版本和 reactive destructure 语义影响。升级测试应关注 default 行为与类型，而不是只锁一段字符串。

### 4. Template 生成结果

稳定的结构判断：

| 源节点 | 预期编译知识 |
| --- | --- |
| root section 动态 class | `CLASS` |
| native input `v-model` | DOM model directive/更新 listener，并可能需要 hydration/runtime directive 路径 |
| `v-if/v-else` | conditional branches，分支 identity |
| `v-for` + stable key | `KEYED_FRAGMENT` |
| TicketRow | 已解析 setup component；ticket/selected/onSelect 为动态 contract |
| footer | 在允许 hoist/static cache 的 options 下可提升 |

生成代码大体包含：

```text
helper imports/aliases
hoisted static constants
render/setup-return render function
openBlock/createElementBlock
withDirectives(vModelText)
conditional branch
renderList(visible, ticket => ...)
createVNode(TicketRow, ...)
patch flag comments in dev output
```

`ticket` 是 renderList callback parameter，属于 v-for local scope；compiler 不能改成 `_ctx.ticket`。`visible`、`selectedId` 等来自 setup/props binding metadata，访问形式由 SFC 组合输出决定。

### 5. 两个变体

#### 删除 key

```text
KEYED_FRAGMENT → UNKEYED_FRAGMENT
```

列表仍可能显示正确文本，但 renderer 以位置 patch，含局部状态的 TicketRow 在插入/排序时可能串实例。正确性测试必须覆盖重排，而不是只对初始 HTML snapshot。

#### `v-bind="ticket"`

compiler 不再静态知道 spread 对象有哪些 props，通常需要 `FULL_PROPS` 路径；它还可能把 `id/title/urgent` 全部作为组件 props 输入，模糊 TicketRow 公开契约。

这不表示禁止 spread。若 wrapper 的定义就是透传一组稳定 props，spread 可读性更好；性能敏感 10,000 行列表应以 production profile 决定。

### 6. Scoped style 输出

概念结果：

```css
.tickets[data-v-ticket-list] { container-type: inline-size; }
.tickets.empty[data-v-ticket-list] { opacity: 0.7; }
.tickets[data-v-ticket-list] .ticket-row { min-block-size: 2.5rem; }
```

exact scope hash/id normalization以实际 output 为准。`:deep(.ticket-row)` 的 inner selector 不再加当前 scope attribute，而祖先 `.tickets` 仍受 scope 限定。这依然是普通 CSS selector；全局 cascade、specificity、source order 都成立。

### 7. Runtime 行为测试

不要尝试手工 eval 任意 generated string。最可靠方式是把 fixture 放入真实 Vite test project，由官方 plugin 组合 script/template/style，再用 VTU/Playwright：

```ts
it('keeps row identity while filtering and reordering', async () => {
  const wrapper = mount(TicketList, {
    props: { tickets: initialTickets, selectedId: 'A', query: '' },
  })

  const before = rowTokensById(wrapper)
  await wrapper.setProps({ tickets: reorderedTickets })
  const after = rowTokensById(wrapper)

  expect(after.get('A')).toBe(before.get('A'))
  expect(after.get('B')).toBe(before.get('B'))
})
```

同时保存 compiler artifacts 与 runtime behavior，升级时可区分：

- generated code changed, behavior same；
- optimization flag changed, performance needs remeasure；
- behavior changed, potential regression。

### 8. 生产边界

- SFC compiler API 可作为工具依赖，但 internal AST/codegen shape 仍需版本 pin；
- runtime 与 compiler 版本应匹配；
- 不把生成代码快照数量当正确性；
- 不 eval 用户 SFC；
- preprocessor、SSR、source maps 要分别跑 fixture；
- compileScript output 不应手工修改后无 source map 交给 bundler。

---

## 练习 2 参考答案：SFC 安全与可维护性诊断器

### 1. 设计边界

工具能证明：template AST 中出现了某种语法。

工具不能单独证明：

- 数据一定可信/不可信；
- sanitizer 配置正确；
- 间接 composable 没有 `Date.now()`；
- 后端授权正确；
- SSR 一定无 mismatch。

因此 diagnostics 文案要可行动，不声称“扫描通过即安全”。

### 2. 完整核心实现

实现使用 `@babel/parser` 做 template expression 窄解析。项目应把它声明为直接 devDependency，不能依赖 compiler-sfc 的传递依赖。

```ts
import { parseExpression } from '@babel/parser'
import {
  NodeTypes,
  parse as parseTemplate,
  type DirectiveNode,
  type ElementNode,
  type RootNode,
  type SimpleExpressionNode,
  type TemplateChildNode,
} from '@vue/compiler-dom'
import {
  parse as parseSfc,
  type SFCBlock,
} from '@vue/compiler-sfc'

export type Rule =
  | 'security/no-raw-v-html'
  | 'correctness/require-v-for-key'
  | 'ssr/no-nondeterministic-template'
  | 'compiler/parse-error'

export interface SfcDiagnostic {
  filename: string
  rule: Rule
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

interface AstNode {
  type: string
  [key: string]: unknown
}

function isAstNode(value: unknown): value is AstNode {
  return Boolean(
    value &&
    typeof value === 'object' &&
    'type' in value &&
    typeof (value as { type?: unknown }).type === 'string',
  )
}

function sourcePosition(source: string, offset: number) {
  const before = source.slice(0, Math.max(0, offset))
  const lines = before.split(/\r\n|\r|\n/)
  const line = lines.length
  const column = (lines[lines.length - 1]?.length ?? 0) + 1
  const sourceLine = source.split(/\r\n|\r|\n/)[line - 1] ?? ''
  return { line, column, sourceLine }
}

function directive(element: ElementNode, name: string): DirectiveNode | undefined {
  return element.props.find(
    (prop): prop is DirectiveNode =>
      prop.type === NodeTypes.DIRECTIVE && prop.name === name,
  )
}

function hasKey(element: ElementNode): boolean {
  return element.props.some(prop => {
    if (prop.type === NodeTypes.ATTRIBUTE) return prop.name === 'key'
    return (
      prop.type === NodeTypes.DIRECTIVE &&
      prop.name === 'bind' &&
      prop.arg?.type === NodeTypes.SIMPLE_EXPRESSION &&
      prop.arg.isStatic &&
      prop.arg.content === 'key'
    )
  })
}

function memberName(node: unknown): string | null {
  if (!isAstNode(node)) return null
  if (node.type === 'Identifier' && typeof node.name === 'string') {
    return node.name
  }
  if (
    (node.type === 'MemberExpression' || node.type === 'OptionalMemberExpression') &&
    node.computed === false
  ) {
    const object = memberName(node.object)
    const property = memberName(node.property)
    return object && property ? `${object}.${property}` : null
  }
  return null
}

function parseJsExpression(content: string): AstNode | null {
  try {
    const result: unknown = parseExpression(content, {
      sourceType: 'module',
      plugins: ['typescript'],
    })
    return isAstNode(result) ? result : null
  } catch {
    return null
  }
}

function isAllowedSanitizer(
  expression: string,
  allowed: ReadonlySet<string>,
): boolean {
  const root = parseJsExpression(expression)
  return Boolean(
    root &&
    (root.type === 'CallExpression' || root.type === 'OptionalCallExpression') &&
    allowed.has(memberName(root.callee) ?? ''),
  )
}

function collectSimpleForBindings(
  forDirective: DirectiveNode | undefined,
): Set<string> {
  const names = new Set<string>()
  const result = forDirective?.forParseResult
  for (const alias of [result?.value, result?.key, result?.index]) {
    if (!alias) continue
    // 本参考实现完整支持普通 identifier；解构 alias 交由 vue-eslint-parser 版本。
    const content = alias.content.trim()
    if (/^[A-Za-z_$][\w$]*$/.test(content)) names.add(content)
  }
  return names
}

function nondeterministicReasons(
  expression: string,
  scope: ReadonlySet<string>,
): string[] {
  const root = parseJsExpression(expression)
  if (!root) return []

  const reasons = new Set<string>()
  const browserGlobals = new Set(['window', 'document', 'localStorage'])

  function visit(node: unknown, parent?: AstNode, edge?: string): void {
    if (Array.isArray(node)) {
      for (const child of node) visit(child, parent, edge)
      return
    }
    if (!isAstNode(node)) return

    if (node.type === 'CallExpression' || node.type === 'OptionalCallExpression') {
      const called = memberName(node.callee)
      if (called === 'Math.random' || called === 'Date.now') reasons.add(called)
    }

    if (node.type === 'Identifier' && typeof node.name === 'string') {
      const isStaticMemberProperty =
        parent &&
        (parent.type === 'MemberExpression' ||
          parent.type === 'OptionalMemberExpression') &&
        edge === 'property' &&
        parent.computed === false
      const isObjectKey =
        parent &&
        (parent.type === 'ObjectProperty' || parent.type === 'ObjectMethod') &&
        edge === 'key' &&
        parent.computed === false

      if (
        !isStaticMemberProperty &&
        !isObjectKey &&
        browserGlobals.has(node.name) &&
        !scope.has(node.name)
      ) {
        reasons.add(node.name)
      }
    }

    for (const [key, value] of Object.entries(node)) {
      if (['type', 'loc', 'start', 'end', 'extra', 'comments'].includes(key)) continue
      if (isAstNode(value) || Array.isArray(value)) visit(value, node, key)
    }
  }

  visit(root)
  return [...reasons].sort()
}

function auditTemplate(
  root: RootNode,
  block: SFCBlock,
  wholeSource: string,
  filename: string,
  options: AuditOptions,
): SfcDiagnostic[] {
  const diagnostics: SfcDiagnostic[] = []
  const allowed = new Set(options.allowSanitizerNames ?? ['sanitizeHtml'])

  function report(
    node: { loc: { start: { offset: number } } },
    rule: Rule,
    severity: 'error' | 'warning',
    message: string,
  ): void {
    const offset = block.loc.start.offset + node.loc.start.offset
    const position = sourcePosition(wholeSource, offset)
    diagnostics.push({
      filename,
      rule,
      severity,
      message,
      line: position.line,
      column: position.column,
      source: position.sourceLine,
    })
  }

  function scanExpression(
    expression: SimpleExpressionNode | undefined,
    scope: ReadonlySet<string>,
  ): void {
    if (!options.ssr || !expression) return
    const reasons = nondeterministicReasons(expression.content, scope)
    if (reasons.length > 0) {
      report(
        expression,
        'ssr/no-nondeterministic-template',
        'warning',
        `SSR template expression uses ${reasons.join(', ')}`,
      )
    }
  }

  function visitChildren(
    children: readonly TemplateChildNode[],
    inheritedScope: ReadonlySet<string>,
  ): void {
    for (const child of children) {
      if (child.type === NodeTypes.INTERPOLATION) {
        scanExpression(child.content, inheritedScope)
        continue
      }
      if (child.type !== NodeTypes.ELEMENT) continue

      const forDirective = directive(child, 'for')
      const localScope = new Set(inheritedScope)
      for (const name of collectSimpleForBindings(forDirective)) localScope.add(name)

      if (forDirective && !hasKey(child)) {
        report(
          forDirective,
          'correctness/require-v-for-key',
          'error',
          'v-for requires a key on the repeated element or <template v-for>.',
        )
      }

      const html = directive(child, 'html')
      if (
        html &&
        (!html.exp || !isAllowedSanitizer(html.exp.content, allowed))
      ) {
        report(
          html,
          'security/no-raw-v-html',
          'error',
          `v-html must call one of: ${[...allowed].join(', ')}`,
        )
      }

      for (const prop of child.props) {
        if (prop.type !== NodeTypes.DIRECTIVE || !prop.exp) continue
        if (prop.name === 'for') {
          scanExpression(prop.forParseResult?.source, inheritedScope)
        } else {
          scanExpression(prop.exp, localScope)
        }
      }

      visitChildren(child.children, localScope)
    }
  }

  visitChildren(root.children, new Set())
  return diagnostics
}

export function auditVueSfc(
  source: string,
  filename: string,
  options: AuditOptions,
): readonly SfcDiagnostic[] {
  const result: SfcDiagnostic[] = []

  try {
    const parsed = parseSfc(source, { filename, sourceMap: false })
    for (const error of parsed.errors) {
      const loc =
        typeof error === 'object' &&
        error !== null &&
        'loc' in error
          ? (error as { loc?: { start?: { offset?: number } } }).loc
          : undefined
      const position = sourcePosition(source, loc?.start?.offset ?? 0)
      result.push({
        filename,
        rule: 'compiler/parse-error',
        severity: 'error',
        message: error instanceof Error ? error.message : String(error),
        line: position.line,
        column: position.column,
        source: position.sourceLine,
      })
    }

    const block = parsed.descriptor.template
    if (!block) return sortDiagnostics(result)

    const templateErrors: Array<{
      message: string
      loc?: { start?: { offset?: number } }
    }> = []
    const root = parseTemplate(block.content, {
      onError(error) {
        templateErrors.push(error)
      },
    })

    for (const error of templateErrors) {
      const offset = block.loc.start.offset + (error.loc?.start?.offset ?? 0)
      const position = sourcePosition(source, offset)
      result.push({
        filename,
        rule: 'compiler/parse-error',
        severity: 'error',
        message: error.message,
        line: position.line,
        column: position.column,
        source: position.sourceLine,
      })
    }

    if (templateErrors.length === 0) {
      result.push(...auditTemplate(root, block, source, filename, options))
    }
  } catch (cause) {
    const position = sourcePosition(source, 0)
    result.push({
      filename,
      rule: 'compiler/parse-error',
      severity: 'error',
      message: cause instanceof Error ? cause.message : String(cause),
      line: position.line,
      column: position.column,
      source: position.sourceLine,
    })
  }

  return sortDiagnostics(result)
}

function sortDiagnostics(
  diagnostics: readonly SfcDiagnostic[],
): SfcDiagnostic[] {
  return [...diagnostics].sort(
    (a, b) =>
      a.line - b.line ||
      a.column - b.column ||
      a.rule.localeCompare(b.rule) ||
      a.message.localeCompare(b.message),
  )
}
```

### 3. 诚实声明参考实现的边界

上面实现完整支持普通 identifier 形式的 v-for aliases。解构 alias：

```vue
<li v-for="({ title }, index) in tickets">...</li>
```

应使用 Babel pattern parser 收集 bindings，或更实际地基于 `vue-eslint-parser`/ESLint scope manager 实现。不能为了“零依赖”用一个越来越复杂的正则假装完整。

同样，Babel generic walker 对 arrow function/local bindings 没实现完整 lexical scope；生产版应使用现成 traversal/scope 工具，或把 SSR 规则收窄到明确 member/call patterns。本题要求在 README 列出这个可能的 false positive。

### 4. 为什么 sanitizer 必须是顶层 call

通过：

```vue
<div v-html="sanitizeHtml(article.body)" />
```

不通过：

```vue
<div v-html="raw || sanitizeHtml(fallback)" />
<div v-html="unsafe + 'sanitizeHtml'" />
<div v-html="maybeSafe" />
```

即使顶层 call 通过，也只能证明调用了 allowlisted 函数；还要 code review sanitizer 配置、URL policy、版本更新和 CSP。

如果允许 `security.sanitizeHtml`，必须显式把完整 callee name 加到 allowlist；不能只看 property 名 `sanitizeHtml`，否则任意对象都能伪装。

### 5. v-for key 规则

通过：

```vue
<li v-for="item in items" :key="item.id" />

<template v-for="item in items" :key="item.id">
  <dt>{{ item.name }}</dt>
  <dd>{{ item.value }}</dd>
</template>
```

不通过：

```vue
<template v-for="item in items">
  <li :key="item.id">{{ item.name }}</li>
</template>
```

当 template 每轮产生多个 siblings 时，key 属于 template 分组身份，放在单个 child 不能表达整个 repeated fragment。

工具不自动写 `:key="index"`，因为它无法从语法推断业务身份。诊断应要求开发者选择稳定 ID。

### 6. Loc 映射

template AST offset 从 `block.content` 起算；SFC template block 的 `loc.start.offset` 指向 inner content 起点：

```ts
wholeOffset = block.loc.start.offset + node.loc.start.offset
```

再从整个 source 计算 line/column，可统一处理 template 在 script 后面和 CRLF。用 fixture 验证比假定 line 加法更稳，因为 opening tag 与首行内容可能同行：

```vue
<template><div v-html="raw" /></template>
```

只做 `templateStartLine + localLine` 很容易 column off-by-one。

### 7. 测试样例

```ts
import { describe, expect, it } from 'vitest'
import { auditVueSfc } from './auditVueSfc'

describe('auditVueSfc', () => {
  it('does not scan comments or script strings', () => {
    const source = `<script setup>const text = 'v-html="raw"'</script>
<template><!-- v-html="raw" --><p>{{ text }}</p></template>`
    expect(auditVueSfc(source, 'Safe.vue', { ssr: true })).toEqual([])
  })

  it('requires an actual allowlisted sanitizer call', () => {
    const source = `<template>
  <div v-html="raw + 'sanitizeHtml'" />
  <div v-html="sanitizeHtml(raw)" />
</template>`
    const diagnostics = auditVueSfc(source, 'Html.vue', { ssr: false })
    expect(diagnostics).toHaveLength(1)
    expect(diagnostics[0]).toMatchObject({
      rule: 'security/no-raw-v-html',
      line: 2,
    })
  })

  it('requires key on template v-for itself', () => {
    const source = `<template>
  <template v-for="item in items"><p :key="item.id" /></template>
</template>`
    expect(auditVueSfc(source, 'List.vue', { ssr: false })).toEqual([
      expect.objectContaining({
        rule: 'correctness/require-v-for-key',
        line: 2,
      }),
    ])
  })

  it('reports browser globals only for SSR mode', () => {
    const source = `<template><p>{{ window.innerWidth }} {{ Date.now() }}</p></template>`
    expect(auditVueSfc(source, 'Ssr.vue', { ssr: false })).toEqual([])
    expect(
      auditVueSfc(source, 'Ssr.vue', { ssr: true })
        .some(item => item.rule === 'ssr/no-nondeterministic-template'),
    ).toBe(true)
  })
})
```

Golden fixture 应包含 exact line/column，但 message 只固定 rule-specific 语义；compiler 自身文案可按版本分支审查。

### 8. Reporter

人类格式：

```text
src/Article.vue:12:8 error security/no-raw-v-html
v-html must call one of: sanitizeHtml
  <div v-html="article.body" />
       ^
```

JSON reporter 原样输出 diagnostics array，供 CI/SARIF adapter 使用。不要在日志输出整个不可信 HTML 或 secret-bearing expression；source excerpt 应截断并转义 terminal control characters。

### 9. CI 缓存和 suppression

Cache key：

```text
sha256(file content)
+ audit tool version
+ compiler-sfc/compiler-dom exact version
+ normalized rule config
```

PR 先扫 changed `.vue`，nightly/full build 扫全仓。Changed-only 不能成为唯一门禁，因为共享 config/compiler 升级会影响未改文件。

Suppression 示例：

```html
<!-- vue-audit-disable-next-line security/no-raw-v-html
     owner=content-platform expires=2026-10-01 ticket=SEC-123 -->
```

生产版需真正解析注释并验证 owner/expiry/ticket；过期 suppression 变 error。不要允许无理由永久 `disable-file`。

### 10. 为什么优先 ESLint plugin

这些规则属于静态反馈，不改变产物：

- IDE 可即时显示；
- ESLint 已有 file traversal、cache、suppression、formatters；
- vue-eslint-parser 已处理 template expression 与 scope；
- 不增加 Vite dev/build 输出差异；
- 不会因诊断器崩溃把 render code 改坏。

课程手写版本用于学 AST；落地前应审查 `eslint-plugin-vue` 与组织已有规则，避免重复维护。

### 11. 升级策略

1. 固定 3.5.42 artifacts 与 diagnostics golden；
2. 新 compiler 版本开升级分支；
3. 跑 syntax fixtures、rules、runtime behavior、SSR；
4. 人工审 AST/output diff；
5. 若只有 internal shape 变化，更新 adapter；
6. 若 public behavior 变化，查 migration/release notes 并写 ADR；
7. 不盲目 `-u` 更新全部 snapshot。

### 12. 最终边界

诊断器能提高反馈速度，但真正生产安全仍来自：

- 不编译不可信 template；
- 后端输出编码与授权；
- sanitizer/URL allowlist；
- CSP 与依赖更新；
- SSR request isolation；
- runtime/E2E security tests；
- 有 owner 的异常审计。

高级 compiler 能力不是“会改 AST 炫技”，而是知道编译器可以证明什么、不能证明什么，以及怎样让每条诊断可复现、可升级、可撤销。
