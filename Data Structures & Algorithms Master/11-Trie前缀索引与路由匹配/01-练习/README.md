# 第 11 章练习

本章恰好两题。练习 1 聚焦 Trie 核心机制；练习 2 把同一思想用于可审计的路由索引。先写规范化、冲突和边界契约，再写代码。

## 练习 1：支持删除与补全的 Unicode Trie

实现：

```ts
export declare class Trie {
  insert(word: string): boolean;
  has(word: string): boolean;
  hasPrefix(prefix: string): boolean;
  delete(word: string): boolean;
  suggest(prefix: string, limit: number): string[];
  get size(): number;
}
```

契约：

- key 在所有入口先做 NFC 规范化，再按 Unicode code point 切分；大小写敏感。
- 空字符串不是合法 key，`insert("")` 抛 `RangeError`；空前缀可用于从根枚举。
- 重复插入不增加 `size`，返回 `false`；首次插入返回 `true`。
- 删除不存在的词返回 `false`；删除已有词返回 `true`，且只剪掉不再被其他词共享的节点。
- `suggest` 返回规范化后的完整词，按 code point 对应的 JavaScript 默认字符串顺序排序，最多 `limit` 个；`limit` 必须为非负安全整数。
- 不得用一个 `Set<string>` 代替 Trie 核心结构，也不得在 `has/hasPrefix` 中扫描所有词。

必须提交：

1. 节点类型与三条核心不变量。
2. 完整 strict TypeScript 实现。
3. 空输入、重复词、共享前缀、一个词是另一个词前缀、组合音标 NFC 等测试。
4. 慢速 `Set + filter + sort` oracle，对固定 seed 随机操作序列做差分测试。
5. 复杂度与空间说明，明确 `suggest` 不能只写成 `O(prefixLength)`。

发散问题：若要按使用频率取 Top 10，你会在查询时扫描子树，还是在每个节点缓存 Top K？写出读、写、内存和热度更新的取舍，不要求实现。

## 练习 2：确定优先级且能报告冲突的 RouterIndex

实现教学版路径路由索引：

```ts
export interface RouteMatch {
  readonly routeId: string;
  readonly params: Readonly<Record<string, string>>;
}

export declare class RouterIndex {
  register(pattern: string, routeId: string): void;
  match(pathname: string): RouteMatch | null;
}
```

pattern 只支持三种 segment：

- 静态：`/users/new`
- 单段参数：`/users/:id`
- 终止通配：`/assets/*path`

契约：

- pattern 与 pathname 都必须以 `/` 开始；根路径 `/` 合法。
- 一个尾斜杠被规范化掉，因此 `/users` 与 `/users/` 等价；重复斜杠拒绝。
- pattern 不允许 query/hash；routeId 必须是非空字符串。
- 优先级按首个不同位置比较：静态 > 参数 > 通配。高优先分支无法完整匹配时必须回退。
- 通配符只能在最后，至少可捕获一个 segment；本题不让 `/assets/*path` 匹配 `/assets`。
- 同一节点至多一个参数孩子；若参数名不同则注册冲突。一个 pattern 内参数名不可重复。
- 同一结构重复注册、重复 routeId 均抛出带 pattern/routeId 的冲突错误，禁止静默覆盖。
- 先按原始 `/` 切分，再分别 `decodeURIComponent`；坏转义或解码后含 `/`、NUL 的 segment 明确抛错。
- 最大 32 个 segment、原始 pathname 最大 4096 code units，超限拒绝。
- `match` 只匹配路径，不做 HTTP method、host、认证或资源授权。

必测案例：

```text
/users/new       优先于 /users/:id
/a/c 与 /:name/b 同时存在时，/a/b 应回退并命中参数路由
/assets/*path    捕获 a/logo.svg
坏百分号编码、%2F、重复斜杠、参数冲突、通配不在末尾均失败
```

交付物：路由节点结构、注册和匹配实现、至少 12 个测试、复杂度说明，以及一段“为什么匹配成功不等于授权成功”的生产边界说明。

开放设计：若要同时支持 HTTP method、host、可选 segment 和每条路由自己的参数名，你会扩展当前树、预编译候选，还是直接选择成熟 router？给出 ADR 式取舍，不要求全部编码。
