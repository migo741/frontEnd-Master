# 第 13 章参考答案

## 练习一：推荐路线

20 人、三个领域通常先采用**单仓模块化/工作区 monorepo**，不急于运行时微前端。理由：部署仍可统一，跨域 UI/类型原子修改频繁；微前端的独立发布收益尚未证明，却立刻增加认证、路由、性能和故障面。若未来团队/发布真正独立，再以清晰 feature/package 边界拆运行时。

```text
apps/admin/src/app -> features/order|inventory|support -> entities -> shared
packages/ui (无业务)
packages/contracts (生成/验证 API schema，避免领域逻辑大杂烩)
```

每个 feature 只导出 public API；ESLint 禁止 `/internal/` deep import。app composition root 创建 per-app api/query/store。订单纵切先新增 `features/order-detail`，adapter 从旧 API/Redux 读取但组件只依赖新 facade；灰度双读比较、单写旧路径，验证后切新 query，最后删旧 slice。

localStorage token 迁移需要后端支持 HttpOnly Secure SameSite cookie/短期 token、CSRF 策略、刷新和注销；前端只维护 session 状态，清理旧 token 需兼容窗口和监控。它不是纯前端重构。

## 练习二：门禁要点

`react/react-dom` 作为 peerDependencies，声明支持范围并用矩阵消费者项目验证；交互组件入口保留 `'use client'` 且构建器不剥离，纯 token/服务器安全入口可单独导出。每个子路径 export：`@company/ui/button`，CSS sideEffects 精确标记。

PR 门禁：type/lint/unit → Story interaction/RTL/axe → consumer Vite/Next build → bundle diff → 关键视觉。发布用 changeset 生成 changelog；破坏变更先新增替代 API、旧 prop runtime warning/codemod、至少一个约定周期后 major 删除。

差 API：`<Button primary danger small link />` 允许冲突。兼容期新增：

```ts
type NewButtonProps = {
  variant?: 'solid' | 'outline' | 'danger' | 'link'
  size?: 'sm' | 'md' | 'lg'
}
```

adapter 仅在旧 prop 存在时映射并警告；同时传新旧 prop 报错/新 prop 优先须文档明确。codemod 转换常见组合，遥测/代码搜索确认旧用法为零后 major 删除。

严重漏洞：组件/依赖 SBOM 定位所有版本；建最小复现与补丁，发 security advisory 和 patched patch/minor；自动 PR 消费者，核心应用灰度并监控；无法升级者提供临时缓解但设期限；复盘增加相应回归测试和升级 SLA。

