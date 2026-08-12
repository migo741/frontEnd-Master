# 第 04 章答案

## 练习 1：路径不可变更新

### 因果链

先沿路径收集每一层容器与键，但不修改任何对象。

更新叶子后若 SameValue 未变，可直接返回旧根。

否则从叶子向根回建，每层只浅复制一次，并把新的子节点装回去。

这保证变化路径换身份、旁支保身份。

### 可复制实现

```js
const blocked = new Set(["__proto__", "prototype", "constructor"]);

function assertContainer(value, at) {
  const plain = value !== null &&
    (Array.isArray(value) || Object.getPrototypeOf(value) === Object.prototype ||
     Object.getPrototypeOf(value) === null);
  if (!plain) throw new TypeError(`Non-container at path index ${at}`);
}

export function updateAtPath(root, path, updater) {
  if (!Array.isArray(path)) throw new TypeError("path must be an array");
  if (typeof updater !== "function") throw new TypeError("updater must be a function");
  if (path.length === 0) return updater(root);

  const frames = [];
  let cursor = root;

  for (let i = 0; i < path.length; i += 1) {
    assertContainer(cursor, i);
    const key = path[i];
    if (typeof key === "string" && blocked.has(key)) throw new TypeError(`Blocked key: ${key}`);
    if (Array.isArray(cursor) && (!Number.isInteger(key) || key < 0)) {
      throw new TypeError(`Array index required at path index ${i}`);
    }
    if (!Object.prototype.hasOwnProperty.call(cursor, key)) {
      throw new RangeError(`Missing path segment: ${String(key)}`);
    }
    frames.push([cursor, key]);
    cursor = cursor[key];
  }

  let child = updater(cursor);
  if (Object.is(child, cursor)) return root;

  for (let i = frames.length - 1; i >= 0; i -= 1) {
    const [parent, key] = frames[i];
    const clone = Array.isArray(parent)
      ? parent.slice()
      : Object.assign(Object.create(Object.getPrototypeOf(parent)), parent);
    clone[key] = child;
    child = clone;
  }
  return child;
}
```

### 测试要点

```js
const before = { user: { name: "A" }, settings: { dark: true } };
const after = updateAtPath(before, ["user", "name"], () => "B");

assert.notEqual(after, before);
assert.notEqual(after.user, before.user);
assert.equal(after.settings, before.settings);
assert.equal(before.user.name, "A");
```

测试 updater 返回同一对象、NaN 到 NaN 返回原根、0 到 -0 创建新路径。

稀疏数组使用 slice 后仍应保持 hole，不应变成显式 undefined。

### 边界与复写任务

参考实现通过普通赋值回建，因此不会保留路径属性的特殊 descriptor。

契约已限制为应用状态普通对象；若要处理领域对象，应明确 descriptor 与原型策略，而不是悄悄扩展。

合上答案重写，再实现 `removeAtPath`，要求仍保持结构共享且数组删除语义明确。

## 练习 2：自动保存状态机

### 状态设计

`dirty` 与 `saving` 是两个正交事实，不应挤进一个 phase。

dirty 由当前编辑版本是否大于已保存版本派生。

在途请求保存自己的文本与版本，因此完成时知道它真正确认了什么。

### 可复制实现

```js
export function initialSaveState(text = "") {
  return Object.freeze({
    text,
    editVersion: 0,
    savedVersion: 0,
    request: null,
    error: null,
  });
}

export const isDirty = (state) => state.editVersion > state.savedVersion;
export const isSaving = (state) => state.request !== null;

export function transition(state, event) {
  switch (event.type) {
    case "EDITED": {
      if (Object.is(event.text, state.text)) return { state, commands: [] };
      return {
        state: {
          ...state,
          text: event.text,
          editVersion: state.editVersion + 1,
          error: null,
        },
        commands: [],
      };
    }

    case "SAVE_REQUESTED": {
      if (!isDirty(state) || isSaving(state)) return { state, commands: [] };
      if (typeof event.requestId !== "string" || event.requestId === "") {
        throw new TypeError("requestId must be a non-empty string");
      }
      const request = {
        id: event.requestId,
        version: state.editVersion,
        text: state.text,
      };
      return {
        state: { ...state, request, error: null },
        commands: [{ type: "SAVE", ...request }],
      };
    }

    case "SAVE_SUCCEEDED": {
      const request = state.request;
      if (!request || request.id !== event.requestId || request.version !== event.version) {
        return { state, commands: [] };
      }
      return {
        state: {
          ...state,
          savedVersion: Math.max(state.savedVersion, request.version),
          request: null,
          error: null,
        },
        commands: [],
      };
    }

    case "SAVE_FAILED": {
      const request = state.request;
      if (!request || request.id !== event.requestId || request.version !== event.version) {
        return { state, commands: [] };
      }
      return {
        state: { ...state, request: null, error: event.error },
        commands: [],
      };
    }

    default:
      return { state, commands: [] };
  }
}
```

### 关键事件序列

1. 初始状态 SAVE_REQUESTED：无命令，身份不变。
2. EDITED A → SAVE_REQUESTED r1：命令保存版本 1 的 A。
3. r1 在途时 EDITED B：版本变 2，请求快照仍是 A/1。
4. r1 成功：savedVersion 为 1，当前仍 dirty。
5. 再请求 r2 并成功：savedVersion 为 2，变为 clean。
6. r1 成功事件再次到达：requestId 不匹配，原状态原样返回。
7. r2 失败：清除在途请求、保留文本和 dirty，允许重试。

### 始终成立的不变量

- `0 <= savedVersion <= editVersion`。
- request 不为空时，`request.version <= editVersion`。
- 每次 transition 至多产生一个 command。
- 过期响应不改变任何状态身份。
- 保存失败不回退用户文本与 editVersion。

可用随机事件序列不断断言这些不变量。

### 边界与复写任务

若服务端会规范化文本，成功事件还需携带 serverText，并规定用户已继续编辑时是否合并。

多标签页还需要服务端版本/ETag，单机 editVersion 不能解决分布式冲突。

合上答案重写，然后增加 `DISCARD_LOCAL_CHANGES`；明确在有请求进行时应拒绝、取消还是生成补偿命令。
