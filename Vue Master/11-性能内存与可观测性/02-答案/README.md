# 答案与复盘

## 题 1

先按同一设备/网络记录 trace 和 waterfall，并从 RUM 按 route/device/release 分段。LCP 若被 900KB 非首屏图表库阻塞，路由/组件拆分才有证据；INP trace 若显示筛选同步重算 10k 行并 patch 全表，应先索引/worker/虚拟化和稳定 row props；若主要是 layout，检查 DOM 数与读写交错。

五天可选三项：移出首屏图表/编辑器 chunk；将筛选计算移到 worker 并只回传 id；窗口化表格并稳定行 props。预算示例：关键路由初始 JS ≤ 350KB gzip、LCP p75 ≤ 2.5s、INP p75 ≤ 200ms、CLS ≤ 0.1；CI 检 bundle，预发跑固定 trace，发布后看 RUM 对照组。数字需按产品实际基线调整。

## 题 2

自动重复“进入地图 → 操作 → 离开”10 次，每轮等待空闲并在可控条件下触发 GC，取 baseline 与末次 heap snapshot；用 comparison 找增长构造器，再沿 retaining path 找 owner。候选包括 window listener、Resize/IntersectionObserver、setInterval、地图 SDK 实例、WebSocket、detached DOM、闭包内大 GeoJSON、未设上限的 cache、KeepAlive 未 deactivate 的 effect。

修复不是把变量设 null 就结束：调用 SDK destroy、成对 cleanup、限制 cache、必要时在 `onDeactivated` 暂停。验收为重复 20 次后 retained instances/DOM/listeners 回到稳定平台，业务交互仍正确，并补自动化生命周期测试或开发期资源计数。

