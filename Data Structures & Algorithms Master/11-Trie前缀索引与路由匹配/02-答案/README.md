# 第 11 章参考答案

参考答案先给可验证的慢模型，再推导索引。代码强调不变量；真实项目优先使用成熟路由器和搜索组件。

## 练习 1：Unicode Trie

### 1. 慢速 oracle

`Set<string>` 足以表达业务语义，适合验证优化结构：

```ts
const normalizeWord = (value: string): string => value.normalize("NFC");

function suggestSlow(
  words: ReadonlySet<string>,
  prefix: string,
  limit: number,
): string[] {
  const normalized = normalizeWord(prefix);
  return [...words]
    .filter((word) => word.startsWith(normalized))
    .sort()
    .slice(0, limit);
}
```

它每次建议都扫描全部词，时间约 `O(nL + n log n)`，不适合高频大词典，却容易读懂，可作为随机测试 oracle。

### 2. 推导与实现

每个节点保存孩子与终止标记。为了重建建议结果，DFS 携带从根到当前节点的 token 数组。删除时保存向下走过的路径，再反向剪枝。

```ts
interface TrieNode {
  terminal: boolean;
  readonly children: Map<string, TrieNode>;
}

function createNode(): TrieNode {
  return { terminal: false, children: new Map<string, TrieNode>() };
}

function tokensOf(value: string): string[] {
  return [...value.normalize("NFC")];
}

export class Trie {
  readonly #root: TrieNode = createNode();
  #size = 0;

  get size(): number {
    return this.#size;
  }

  insert(word: string): boolean {
    const normalized = word.normalize("NFC");
    if (normalized.length === 0) throw new RangeError("word must not be empty");

    let node = this.#root;
    for (const token of tokensOf(normalized)) {
      let child = node.children.get(token);
      if (child === undefined) {
        child = createNode();
        node.children.set(token, child);
      }
      node = child;
    }

    if (node.terminal) return false;
    node.terminal = true;
    this.#size += 1;
    return true;
  }

  has(word: string): boolean {
    if (word.normalize("NFC").length === 0) return false;
    const node = this.#find(tokensOf(word));
    return node?.terminal === true;
  }

  hasPrefix(prefix: string): boolean {
    return this.#find(tokensOf(prefix)) !== undefined;
  }

  delete(word: string): boolean {
    const normalized = word.normalize("NFC");
    if (normalized.length === 0) return false;

    const path: Array<{ parent: TrieNode; token: string; child: TrieNode }> = [];
    let node = this.#root;
    for (const token of tokensOf(normalized)) {
      const child = node.children.get(token);
      if (child === undefined) return false;
      path.push({ parent: node, token, child });
      node = child;
    }
    if (!node.terminal) return false;

    node.terminal = false;
    this.#size -= 1;

    for (let index = path.length - 1; index >= 0; index -= 1) {
      const step = path[index];
      if (step === undefined) throw new Error("unreachable path index");
      if (step.child.terminal || step.child.children.size > 0) break;
      step.parent.children.delete(step.token);
    }
    return true;
  }

  suggest(prefix: string, limit: number): string[] {
    if (!Number.isSafeInteger(limit) || limit < 0) {
      throw new RangeError("limit must be a non-negative safe integer");
    }
    if (limit === 0) return [];

    const normalized = prefix.normalize("NFC");
    const prefixTokens = tokensOf(normalized);
    const start = this.#find(prefixTokens);
    if (start === undefined) return [];

    const results: string[] = [];
    const visit = (node: TrieNode, path: string[]): void => {
      if (results.length >= limit) return;
      if (node.terminal) results.push(path.join(""));

      const entries = [...node.children.entries()].sort(([a], [b]) =>
        a < b ? -1 : a > b ? 1 : 0,
      );
      for (const [token, child] of entries) {
        if (results.length >= limit) break;
        path.push(token);
        visit(child, path);
        path.pop();
      }
    };

    visit(start, [...prefixTokens]);
    return results;
  }

  #find(tokens: readonly string[]): TrieNode | undefined {
    let node = this.#root;
    for (const token of tokens) {
      const child = node.children.get(token);
      if (child === undefined) return undefined;
      node = child;
    }
    return node;
  }
}
```

`suggest` 中使用递归是为了可读性。若外部 key 长度无上限，深链可能耗尽 JavaScript 调用栈；生产实现应限制 key 长度或改为显式栈。

### 3. 正确性

- 插入：每轮结束后，当前节点正好表示已消费 token 前缀；终止时标记的节点正好表示完整 key。
- 查询：若任一边缺失，则该前缀未被任何已插入 key 建立；所有边存在且终止标记为真，才有完整 key。
- 删除：反向阶段只删除“非终止且无孩子”的节点，因此不会破坏任何其他完整 key；遇到共享节点立即停止。
- 建议：DFS 只访问前缀节点子树，该子树中的终止节点与拥有该前缀的 key 一一对应；按孩子 token 排序的先序遍历给出约定的词典序。

### 4. 复杂度

设 key token 数为 `m`，前缀 token 数为 `p`，为得到 `k` 个结果实际访问的子树节点数为 `z`：

| 操作 | 时间 | 辅助空间 |
| --- | --- | --- |
| insert/has | 期望 `O(m)` | 临时 token `O(m)` |
| delete | 期望 `O(m)` | 路径 `O(m)` |
| hasPrefix | 期望 `O(p)` | token `O(p)` |
| suggest | `O(p + z + 排序孩子成本)` | DFS 深度与输出 |

代码为确定输出顺序而在每个访问节点排序孩子。若词典序查询极频繁，可维护有序孩子结构或在批量构建后冻结排序，但写入成本随之增加。

### 5. 测试示例

```ts
import assert from "node:assert/strict";
import test from "node:test";

test("shared prefixes survive deletion", () => {
  const trie = new Trie();
  assert.equal(trie.insert("car"), true);
  assert.equal(trie.insert("card"), true);
  assert.equal(trie.insert("cat"), true);
  assert.equal(trie.insert("car"), false);
  assert.deepEqual(trie.suggest("ca", 10), ["car", "card", "cat"]);
  assert.equal(trie.delete("car"), true);
  assert.equal(trie.has("car"), false);
  assert.equal(trie.has("card"), true);
});

test("normalizes canonically equivalent words", () => {
  const trie = new Trie();
  trie.insert("e\u0301");
  assert.equal(trie.has("é"), true);
  assert.deepEqual(trie.suggest("é", 1), ["é"]);
});
```

随机测试维护一个已规范化的 `Set`。每步随机 insert/delete/has/suggest，并将 Trie 结果与慢 oracle 比较；失败时输出 seed 与最短操作序列。

## 练习 2：RouterIndex

### 1. 先用慢模型澄清语义

最容易验证的版本是把每个 pattern 编译为 segment 描述，匹配时遍历所有 route，收集完整匹配，再按逐段 specificity 与注册时稳定序号选最优。它的查询为 `O(routes × segments)`，但非常适合成为优化版 oracle。

树索引共享静态与参数前缀，避免每次扫描所有路由。关键不是“完全没有回溯”，而是按静态、参数、通配顺序深度探索，返回第一个完整匹配。

### 2. 类型与解析

```ts
interface RouteRecord {
  readonly routeId: string;
  readonly pattern: string;
}

interface ParamEdge {
  readonly name: string;
  readonly node: RouteNode;
}

interface WildcardRoute {
  readonly name: string;
  readonly record: RouteRecord;
}

interface RouteNode {
  readonly statics: Map<string, RouteNode>;
  param?: ParamEdge;
  wildcard?: WildcardRoute;
  route?: RouteRecord;
}

function newRouteNode(): RouteNode {
  return { statics: new Map<string, RouteNode>() };
}

type PatternPart =
  | { readonly kind: "static"; readonly value: string }
  | { readonly kind: "param"; readonly name: string }
  | { readonly kind: "wildcard"; readonly name: string };

function canonicalSegments(raw: string, source: "pattern" | "pathname"): string[] {
  if (!raw.startsWith("/")) throw new TypeError(`${source} must start with /`);
  if (raw.length > 4096) throw new RangeError(`${source} is too long`);
  if (source === "pattern" && (raw.includes("?") || raw.includes("#"))) {
    throw new TypeError("pattern must not contain query or hash");
  }
  if (raw.includes("//")) throw new TypeError(`${source} contains an empty segment`);

  const withoutTrailing = raw.length > 1 && raw.endsWith("/") ? raw.slice(0, -1) : raw;
  const encoded = withoutTrailing === "/" ? [] : withoutTrailing.slice(1).split("/");
  if (encoded.length > 32) throw new RangeError(`${source} has too many segments`);

  return encoded.map((segment) => {
    let decoded: string;
    try {
      decoded = decodeURIComponent(segment);
    } catch {
      throw new URIError(`${source} contains invalid percent encoding`);
    }
    if (decoded.includes("/") || decoded.includes("\0")) {
      throw new URIError(`${source} segment decodes to a forbidden character`);
    }
    return decoded;
  });
}

function parsePattern(pattern: string): PatternPart[] {
  const segments = canonicalSegments(pattern, "pattern");
  const names = new Set<string>();
  return segments.map((segment, index) => {
    if (segment.startsWith(":")) {
      const name = segment.slice(1);
      if (name.length === 0 || names.has(name)) throw new TypeError("invalid parameter name");
      names.add(name);
      return { kind: "param", name };
    }
    if (segment.startsWith("*")) {
      const name = segment.slice(1);
      if (name.length === 0 || names.has(name) || index !== segments.length - 1) {
        throw new TypeError("wildcard must be named, unique, and terminal");
      }
      names.add(name);
      return { kind: "wildcard", name };
    }
    return { kind: "static", value: segment };
  });
}
```

教学契约把以 `:` 或 `*` 开头的 segment 保留给语法；若产品需要字面量冒号，应另行设计转义，不应猜测。

### 3. 参考实现

```ts
export interface RouteMatch {
  readonly routeId: string;
  readonly params: Readonly<Record<string, string>>;
}

export class RouterIndex {
  readonly #root: RouteNode = newRouteNode();
  readonly #routeIds = new Set<string>();

  register(pattern: string, routeId: string): void {
    if (routeId.length === 0) throw new TypeError("routeId must not be empty");
    if (this.#routeIds.has(routeId)) throw new Error(`duplicate routeId: ${routeId}`);

    const parts = parsePattern(pattern);
    let node = this.#root;

    for (const part of parts) {
      if (part.kind === "static") {
        let child = node.statics.get(part.value);
        if (child === undefined) {
          child = newRouteNode();
          node.statics.set(part.value, child);
        }
        node = child;
      } else if (part.kind === "param") {
        if (node.param !== undefined && node.param.name !== part.name) {
          throw new Error(`parameter conflict at ${pattern}: :${node.param.name} vs :${part.name}`);
        }
        if (node.param === undefined) node.param = { name: part.name, node: newRouteNode() };
        node = node.param.node;
      } else {
        if (node.wildcard !== undefined) {
          throw new Error(`wildcard conflict: ${pattern}`);
        }
        node.wildcard = { name: part.name, record: { routeId, pattern } };
        this.#routeIds.add(routeId);
        return;
      }
    }

    if (node.route !== undefined) throw new Error(`duplicate route shape: ${pattern}`);
    node.route = { routeId, pattern };
    this.#routeIds.add(routeId);
  }

  match(pathname: string): RouteMatch | null {
    const segments = canonicalSegments(pathname, "pathname");

    const search = (
      node: RouteNode,
      index: number,
      params: Readonly<Record<string, string>>,
    ): RouteMatch | null => {
      if (index === segments.length) {
        return node.route === undefined
          ? null
          : { routeId: node.route.routeId, params };
      }

      const segment = segments[index];
      if (segment === undefined) throw new Error("unreachable segment index");

      const staticChild = node.statics.get(segment);
      if (staticChild !== undefined) {
        const result = search(staticChild, index + 1, params);
        if (result !== null) return result;
      }

      if (node.param !== undefined) {
        const result = search(node.param.node, index + 1, {
          ...params,
          [node.param.name]: segment,
        });
        if (result !== null) return result;
      }

      if (node.wildcard !== undefined) {
        return {
          routeId: node.wildcard.record.routeId,
          params: {
            ...params,
            [node.wildcard.name]: segments.slice(index).join("/"),
          },
        };
      }
      return null;
    };

    return search(this.#root, 0, {});
  }
}
```

### 4. 一个容易漏掉的原子性问题

上面实现先沿树创建节点，后面才可能发现深处冲突。如果注册失败，前面创建的空节点可能残留；它们不改变匹配结果，却违反“失败无副作用”的更强生产契约。稳健实现有三种选择：

1. 第一遍只验证整条路径，第二遍提交；
2. 记录本次创建的边，catch 时逆序回滚；
3. 构造持久化/不可变新树，成功后原子替换 root。

练习若承诺注册失败完全不改变内部结构，必须补其中一种。教学参考保留这个缺口，是为了让代码评审关注事务性，而不只关注 happy path。

### 5. 正确性与复杂度

注册维持“同一节点静态 token 唯一、参数至多一条、通配至多一条”的结构不变量。匹配的递归状态完整记录节点、输入位置和参数；每个分支都至少消费一个 segment，最大深度受 32 限制。搜索顺序保证：只有更具体分支无法完成时才尝试较低优先级，因此第一个完整结果符合契约。

设路径段数为 `s`：无回退时常见成本为期望 `O(s)`；存在静态/参数候选时会探索失败分支，最坏取决于路由形状。空间为递归深度和参数副本；本实现每次捕获参数会复制对象，参数很少时简单可靠，极端场景可改为可回滚栈。

### 6. 测试骨架

```ts
test("prefers static and falls back after a failed static suffix", () => {
  const router = new RouterIndex();
  router.register("/users/new", "new-user");
  router.register("/users/:id", "user");
  router.register("/a/c", "static-branch");
  router.register("/:name/b", "fallback");

  assert.deepEqual(router.match("/users/new"), { routeId: "new-user", params: {} });
  assert.deepEqual(router.match("/users/42"), {
    routeId: "user",
    params: { id: "42" },
  });
  assert.deepEqual(router.match("/a/b"), {
    routeId: "fallback",
    params: { name: "a" },
  });
});

test("matches terminal wildcard and rejects unsafe encoding", () => {
  const router = new RouterIndex();
  router.register("/assets/*path", "asset");
  assert.deepEqual(router.match("/assets/icons/logo.svg"), {
    routeId: "asset",
    params: { path: "icons/logo.svg" },
  });
  assert.throws(() => router.match("/assets/a%2Fb"), /forbidden/);
  assert.throws(() => router.match("/assets/%ZZ"), /percent/);
});
```

还应覆盖根路由、尾斜杠、无匹配、通配零 segment、重复 pattern、重复 routeId、参数名冲突、重复参数名、32/33 segment 边界。

### 7. 生产边界

- 路由匹配后必须独立执行认证、租户与资源级授权。
- HTTP method、host、content type、中间件顺序和 404/405 语义不在教学接口内。
- 真实 router 还要处理注册删除、并发热更新、可观测性和框架适配。
- URL 规范化应与代理、Web 服务器保持一致，避免不同层对 `%2F`、重复斜杠和大小写有不同解释。
- 不要把路由参数直接拼 SQL、文件路径或内部 URL；匹配只是解析，不是净化全部下游语义。

复写任务：关闭答案，先重写 `delete` 的反向剪枝，再只看 RouterIndex 接口写出“静态失败后参数回退”的测试与实现。最后用慢速全路由 oracle 随机生成小路由表做差分验证。
