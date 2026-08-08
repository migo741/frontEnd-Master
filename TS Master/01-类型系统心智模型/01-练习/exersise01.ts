// 任务 1：编译器被迫相信的所有前提
//
// - fetch 成功返回 Response（网络层不抛错）
// - response.ok 为 true 时 body 一定是合法 JSON（未检查 content-type）
// - response.json() 解析成功且结果为对象（历史上 DOM 类型常为 any，注解 Promise<User> 只是承诺）
// - 根对象有 id: string
// - 根对象有 profile 且为对象，profile.name 为 string
// - 根对象有 roles 且为 string[]，每个元素为 string
// - roles 至少有一个元素（roles[0] 直接访问时未检查 undefined）
// - profile.name / roles[i] 调用 toUpperCase 时一定是 string 原型链上的方法

type User = { id: string; profile: { name: string }; roles: string[] };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function parseUser(value: unknown, path = "$"): User {
  if (!isRecord(value)) throw new Error(`${path}: expected object`);
  if (typeof value.id !== "string")
    throw new Error(`${path}.id: expected string`);
  if (!isRecord(value.profile))
    throw new Error(`${path}.profile: expected object`);
  if (typeof value.profile.name !== "string") {
    throw new Error(`${path}.profile.name: expected string`);
  }
  if (!Array.isArray(value.roles))
    throw new Error(`${path}.roles: expected array`);
  for (const [index, role] of value.roles.entries()) {
    if (typeof role !== "string")
      throw new Error(`${path}.roles[${index}]: expected string`);
  }
  return {
    id: value.id,
    profile: { name: value.profile.name },
    roles: [...value.roles],
  };
}

async function loadUser(id: string): Promise<User> {
  const response = await fetch(`/api/users/${encodeURIComponent(id)}`);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  const raw: unknown = await response.json();
  return parseUser(raw);
}

async function main() {
  const user = await loadUser("1");
  console.log(user.profile.name.toUpperCase());

  const firstRole = user.roles[0];
  if (firstRole !== undefined) {
    console.log(firstRole.toUpperCase());
  }
}

// 任务 5：5 个坏 payload 测试
function runBadPayloadTests() {
  const cases: Array<{ name: string; payload: unknown; expectedPath: string }> =
    [
      { name: "null", payload: null, expectedPath: "$" },
      { name: "字段缺失", payload: { id: "1" }, expectedPath: "$.profile" },
      {
        name: "嵌套错误",
        payload: { id: "1", profile: { name: 123 }, roles: ["admin"] },
        expectedPath: "$.profile.name",
      },
      {
        name: "roles 非数组",
        payload: { id: "1", profile: { name: "Ada" }, roles: "admin" },
        expectedPath: "$.roles",
      },
      {
        name: "数组元素非字符串",
        payload: { id: "1", profile: { name: "Ada" }, roles: ["admin", 42] },
        expectedPath: "$.roles[1]",
      },
    ];

  for (const { name, payload, expectedPath } of cases) {
    try {
      parseUser(payload);
      throw new Error(`[${name}] 应抛出但未抛出`);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      if (!message.includes(expectedPath)) {
        throw new Error(
          `[${name}] 期望 path 含 ${expectedPath}，实际: ${message}`,
        );
      }
    }
  }
}

runBadPayloadTests();

// 任务 6：类型被擦除后还有哪些安全责任
//
// - 鉴权与授权：类型不证明调用方有权读取该用户
// - HTTP 语义：status、content-type、响应体大小与超时
// - 输入边界：JSON 深度/大小、原型污染、特殊对象（如 __proto__）
// - 业务约束：roles 是否允许为空、id 格式、name 长度等类型无法表达的规则
// - 错误脱敏：不要把内部堆栈或敏感字段泄漏给客户端
// - 网络与可用性：重试、幂等、降级；类型层完全不覆盖
