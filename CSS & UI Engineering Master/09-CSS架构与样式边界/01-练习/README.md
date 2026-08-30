# 练习：从全局污染到稳定样式契约

## 题 1（75 分钟）

重构一个混合 reset、Element Plus/第三方 CSS、全局 `.title`、Vue scoped、utility 和紧急 override 的页面。建立 layer 与模块边界；升级第三方次版本后只允许 adapter 文件变化。

验收：无新增 important；不存在跨 feature 深层 DOM selector；写出允许的样式依赖方向。

## 题 2（60 分钟）

设计一个 Vue/React 都能消费的 `StatusBadge` 样式契约：tone、size、图标、busy、forced-colors。只公开 custom properties、class/data-state 或 Web Component part 中必要部分，并写破坏性变更判定。

