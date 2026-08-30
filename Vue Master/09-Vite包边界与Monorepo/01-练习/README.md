# 练习：Vite 插件与架构守卫

## 题 1（60 分钟）

实现一个 Vite 虚拟模块 `virtual:build-info`，导出 commit、buildTime、appVersion；只允许构建时注入白名单字段，开发时支持 HMR 更新。说明哪些字段绝不能放入其中，并写插件单测思路。

## 题 2（45 分钟）

现有项目允许 `features/order` 深层 import `features/user/internal/cache`。设计 ESLint/构建规则与 public API 目录，阻止跨 feature 深层依赖；画出允许的依赖方向；给一次渐进迁移计划，不能“大爆炸重构”。

