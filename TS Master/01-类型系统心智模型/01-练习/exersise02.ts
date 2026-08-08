// 任务：
// 解释为什么结构类型允许；额外属性检查为什么救不了变量参数。
// 设计 toPublicUser 明确投影，保证运行时真的删除敏感字段。
// 比较 Pick<AdminUser, 'id' | 'name'>、精确对象工具、Schema strip 和显式构造的安全性。
// 写类型测试与 JSON 输出测试。
// 给代码评审规则：何时“可赋值”不等于“允许跨信任边界”。

type PublicUser = {
  id: string;
  name: string;
};
type AdminUser = {
  id: string;
  name: string;
  permissions: string[];
};

class mySet {
  db = new Map();
  constructor() {}
  set(key: string | number, val: any) {
    this.db.set(key, val);
  }
}
const publicCache = new mySet();
function cachePublic(user: PublicUser) {
  publicCache.set(user.id, user);
}
cachePublic(0);
