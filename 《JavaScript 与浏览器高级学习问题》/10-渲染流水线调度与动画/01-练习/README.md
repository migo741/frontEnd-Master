# 第 10 章练习

## 练习一：消灭 2,000 行表格的布局抖动

故意实现一个慢版本：每行先写 width/class，再读取 `getBoundingClientRect()` 计算汇总高度，窗口 resize 时同步跑完整循环。

任务：

- 用 production 页面和固定 2,000 行数据录制基线；
- 从 trace 指出 JS、Recalculate Style、Layout、Paint 各自成本；
- 重构为单次尺寸读取、批量写入、需要时下一阶段统一读取；
- resize 高频事件只保留最新意图，dispose 后不再执行；
- 若只需要 CSS 布局，删除 JS 宽度计算并解释为什么这是更小修复；
- 写自动化断言保证结果尺寸/行数相同，再人工比较 trace；
- 报告最长 task、layout 次数、交互延迟，而非只报总毫秒。

验收：不得把读取简单挪到 `setTimeout` 就宣称完成；必须说明每个阶段为什么仍需要。

## 练习二：可打断的 FLIP 排序（高难）

为一个 100 项卡片网格实现 `animateReorder(container, reorder)`：

- `reorder` 只移动现有 DOM 节点，不重建卡片；
- 批量记录 First，执行一次重排，再批量记录 Last；
- 用 WAAPI transform 播放 Invert → Play，不逐帧读取布局；
- 用户连续点击排序时，新动画从当前视觉状态平滑接管，旧动画全部释放；
- 新增/删除项、容器滚动和已有 CSS transform 有明确策略；
- reduced motion 时立即到最终状态，焦点仍跟随同一实体；
- 用 Performance trace 证明动画阶段没有每帧 layout；
- 测试最终 DOM 顺序、动画取消、缺失 id 和 dispose。

不要求做炫酷效果；要求动画只是状态变化的可取消投影。

## 复盘交付

列出一次你过去称为“JS 卡”的问题，重新区分它到底慢在脚本、样式、布局、绘制、合成还是网络。
